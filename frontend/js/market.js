(function () {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const fmtInt = (value) => Math.round(number(value)).toLocaleString("en-IN");
  const money = (value) => `₹${fmtInt(value)}`;
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
  const colors = ["#e5a126", "#3478e5", "#35a9e9", "#9473cf", "#ed9b25", "#e65b69", "#64748b", "#18a58b", "#d97706", "#60a5fa", "#a78bfa", "#f472b6", "#14b8a6", "#f59e0b"];
  let currentData = null;
  let localitySort = "psf";
  let maxLocalityPsf = Infinity;
  let activeDistribution = null;
  let requestController = null;

  function show(selector, visible) {
    const node = $(selector);
    if (node) node.hidden = !visible;
  }

  function setText(selector, value) {
    const node = $(selector);
    if (node) node.textContent = value;
  }

  function formatCr(inr) {
    const value = number(inr) / 10000000;
    if (!Number.isFinite(value) || value <= 0) return "—";
    return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: value < 1 ? 2 : 1 })} Cr`;
  }

  function formatPsf(value) {
    return number(value) > 0 ? `${money(value)}/sqft` : "—";
  }

  function parseP25P75(data) {
    const raw = String(data.ppsf_range_formatted || "");
    const nums = raw.match(/[\d,]+/g) || [];
    return {
      p25: nums[0] ? Number(nums[0].replaceAll(",", "")) : 0,
      p75: nums[1] ? Number(nums[1].replaceAll(",", "")) : 0
    };
  }

  function setLoading(isLoading) {
    show("#market-status", isLoading);
    const button = $("#btn-analyze");
    if (button) {
      button.disabled = isLoading;
      button.classList.toggle("is-loading", isLoading);
      const span = $("#btn-analyze span");
      if (span) span.textContent = isLoading ? "Analyzing…" : "Analyze Market";
    }
  }

  let availableCities = [];
  let cityLocalitiesIndex = new Map();
  let apiLocalities = [];

  function normalizeLocalityList(value) {
    if (Array.isArray(value)) {
      return value.map((item) => {
        if (typeof item === "string" || typeof item === "number") return String(item).trim();
        if (item && typeof item === "object") return String(item.name || item.locality || item.area || item.label || item.value || "").trim();
        return "";
      }).filter(Boolean);
    }
    if (typeof value === "string") return value.split(/[;,|]/).map((item) => item.trim()).filter(Boolean);
    return [];
  }

  function normalizeCityLocalitySource(source) {
    const map = new Map();
    if (!source) return map;
    if (Array.isArray(source)) {
      source.forEach((item) => {
        if (typeof item === "string" || typeof item === "number") {
          const city = String(item).trim();
          if (city) map.set(city, []);
          return;
        }
        if (!item || typeof item !== "object") return;
        const city = String(item.city || item.name || item.city_name || item.label || item.value || "").trim();
        const localities = normalizeLocalityList(item.localities || item.areas || item.locations || item.locality_list || item.neighborhoods);
        if (city) map.set(city, [...new Set(localities)].sort((a, b) => a.localeCompare(b)));
      });
      return map;
    }
    if (typeof source !== "object") return map;
    for (const wrapperKey of ["cities", "cityLocalities", "city_localities", "data", "locations"]) {
      if (source[wrapperKey] && source[wrapperKey] !== source && typeof source[wrapperKey] === "object") {
        const nested = normalizeCityLocalitySource(source[wrapperKey]);
        if (nested.size) return nested;
      }
    }
    Object.entries(source).forEach(([city, value]) => {
      let localities = value;
      if (value && !Array.isArray(value) && typeof value === "object") {
        localities = value.localities || value.areas || value.locations || value.locality_list || value.neighborhoods || value.locality;
        if (!localities) {
          // Also support city -> { localityName: metadata } maps.
          localities = Object.keys(value).filter((key) => !["city", "city_name", "name", "label", "count", "metadata"].includes(key.toLowerCase()));
        }
      }
      const list = normalizeLocalityList(localities);
      if (list.length || Array.isArray(value) || typeof value === "string") {
        map.set(String(city).trim(), [...new Set(list)].sort((a, b) => a.localeCompare(b)));
      }
    });
    return map;
  }

  function readCityLocalitiesFile() {
    const candidates = [];
    // Classic-script top-level const/let declarations are visible by identifier, but not on window.
    try { if (typeof CITY_LOCALITIES !== "undefined") candidates.push(CITY_LOCALITIES); } catch (_) {}
    try { if (typeof cityLocalities !== "undefined") candidates.push(cityLocalities); } catch (_) {}
    try { if (typeof city_localities !== "undefined") candidates.push(city_localities); } catch (_) {}
    try { if (typeof cityLocalityMap !== "undefined") candidates.push(cityLocalityMap); } catch (_) {}
    try { if (typeof cityToLocalities !== "undefined") candidates.push(cityToLocalities); } catch (_) {}
    candidates.push(
      window.CITY_LOCALITIES, window.cityLocalities, window.city_localities,
      window.CITY_LOCALITY_MAP, window.cityLocalityMap, window.cityToLocalities,
      window.CITY_LOCALITY_DATA
    );
    for (const candidate of candidates) {
      const normalized = normalizeCityLocalitySource(candidate);
      if (normalized.size) return normalized;
    }
    return new Map();
  }

  function exactCityName(city) {
    const query = String(city || "").trim().toLocaleLowerCase();
    return availableCities.find((item) => item.toLocaleLowerCase() === query) || "";
  }

  function findLocalitiesForCity(city) {
    const entry = [...cityLocalitiesIndex.entries()].find(([name]) => name.toLocaleLowerCase() === String(city || "").trim().toLocaleLowerCase());
    return entry ? entry[1] : [];
  }

  function closeSuggestions(input, list) {
    if (list) list.hidden = true;
    if (input) input.setAttribute("aria-expanded", "false");
  }

  function positionAutocomplete(input, list) {
    if (!input || !list) return;
    const shell = input.closest(".input-shell") || input;
    const rect = shell.getBoundingClientRect();
    const margin = 8;
    const maxHeight = Math.min(320, Math.floor(window.innerHeight * 0.55));
    const below = window.innerHeight - rect.bottom - margin;
    const above = rect.top - margin;
    const openAbove = below < Math.min(180, maxHeight) && above > below;
    const available = Math.max(120, Math.min(maxHeight, openAbove ? above : below));
    list.style.position = "fixed";
    list.style.left = `${Math.max(margin, Math.min(rect.left, window.innerWidth - Math.max(220, rect.width) - margin))}px`;
    list.style.width = `${Math.min(Math.max(220, rect.width), window.innerWidth - margin * 2)}px`;
    list.style.maxWidth = `calc(100vw - ${margin * 2}px)`;
    list.style.maxHeight = `${available}px`;
    list.style.top = openAbove ? `${Math.max(margin, rect.top - Math.min(available, list.scrollHeight || maxHeight))}px` : `${Math.min(window.innerHeight - margin, rect.bottom)}px`;
    list.style.zIndex = "2147483000";
  }

  function showSuggestions(input, list, values, onSelect = () => {}, query = input?.value || "") {
    if (!input || !list) return;
    const q = String(query).trim().toLocaleLowerCase();
    const filtered = values.filter((value) => !q || value.toLocaleLowerCase().includes(q));
    if (!filtered.length) {
      closeSuggestions(input, list);
      list.innerHTML = "";
      return;
    }
    list.innerHTML = filtered.map((value, index) => `<button type="button" class="autocomplete-option" role="option" aria-selected="false" data-value="${esc(value)}" data-index="${index}">${esc(value)}</button>`).join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    positionAutocomplete(input, list);
    list.querySelectorAll(".autocomplete-option").forEach((option) => {
      option.addEventListener("mousedown", (event) => event.preventDefault());
      option.addEventListener("click", () => {
        const selected = option.dataset.value || "";
        input.value = selected;
        closeSuggestions(input, list);
        onSelect(selected);
      });
    });
  }

  async function fetchMarketOptions(city = "") {
    const query = city ? `?city=${encodeURIComponent(city)}` : "";
    const response = await fetch(`/api/market/options${query}`, {
      credentials: "same-origin", cache: "no-store", headers: { "Accept": "application/json" }
    });
    if (!response.ok) throw new Error(`Market options request failed (${response.status})`);
    const payload = await response.json();
    if (!payload || payload.success !== true) throw new Error(payload?.error || "Market options unavailable");
    return payload;
  }

  function mergeCityLocalityMap(target, source) {
    for (const [city, localities] of source.entries()) {
      const existingKey = [...target.keys()].find((name) => name.toLocaleLowerCase() === city.toLocaleLowerCase());
      const key = existingKey || city;
      const merged = [...new Set([...(target.get(key) || []), ...localities])]
        .filter(Boolean).sort((a, b) => a.localeCompare(b));
      target.set(key, merged);
    }
    return target;
  }

  async function getLocalitiesForCity(city) {
    const canonical = exactCityName(city) || String(city || "").trim();
    const fromFile = findLocalitiesForCity(canonical);
    let fromApi = [];
    try {
      const payload = await fetchMarketOptions(canonical);
      fromApi = normalizeLocalityList(payload.localities || []);
    } catch (error) {
      console.warn("Could not load dataset-backed localities; using city_localities.js fallback.", error);
    }
    return [...new Set([...fromFile, ...fromApi])].sort((a, b) => a.localeCompare(b));
  }

  async function loadOptions() {
    const cityInput = $("#filter-city");
    const localityInput = $("#filter-locality");
    const cityList = $("#city-suggestions");
    const localityList = $("#locality-suggestions");
    if (!cityInput) return;
    // The market opens in the combined all-cities view every time; browser-restored values
    // must not silently narrow the market to a previous city.
    cityInput.defaultValue = "";
    cityInput.value = "";
    cityInput.setAttribute("autocomplete", "new-password");
    if (localityInput) { localityInput.defaultValue = ""; localityInput.value = ""; localityInput.setAttribute("autocomplete", "new-password"); }

    // Portal suggestion lists to body so cards, sticky containers and grid overflow
    // cannot clip them. Fixed coordinates are recalculated on every open.
    [cityList, localityList].forEach((list) => {
      if (list && list.parentElement !== document.body) document.body.appendChild(list);
    });
    const positionSuggestions = (input, list) => positionAutocomplete(input, list);
    window.addEventListener("resize", () => {
      if (cityList && !cityList.hidden) positionSuggestions(cityInput, cityList);
      if (localityList && !localityList.hidden) positionSuggestions(localityInput, localityList);
    });
    window.addEventListener("scroll", () => {
      if (cityList && !cityList.hidden) positionSuggestions(cityInput, cityList);
      if (localityList && !localityList.hidden) positionSuggestions(localityInput, localityList);
    }, true);

    // Start with the local file, then always merge the backend's actual dataset cities.
    cityLocalitiesIndex = readCityLocalitiesFile();
    availableCities = [...cityLocalitiesIndex.keys()].filter(Boolean);
    try {
      const payload = await fetchMarketOptions();
      const apiCities = normalizeLocalityList(payload.cities || []);
      for (const city of apiCities) {
        if (!availableCities.some((item) => item.toLocaleLowerCase() === city.toLocaleLowerCase())) {
          availableCities.push(city);
        }
        if (!cityLocalitiesIndex.has(city)) cityLocalitiesIndex.set(city, []);
      }
    } catch (error) {
      console.warn("Could not load dataset-backed city options; using city_localities.js fallback.", error);
    }
    availableCities = [...new Set(availableCities)].sort((a, b) => a.localeCompare(b));
    // Blank is a deliberate All Cities selection; never force Gurgaon as default.
    if (!availableCities.length) console.warn("No city options were returned by city_localities.js or /api/market/options.");
    const preferred = exactCityName(cityInput.value);
    cityInput.value = preferred || "";

    const refreshLocalities = async (city, clearValue = false) => {
      if (clearValue && localityInput) localityInput.value = "";
      apiLocalities = city ? await getLocalitiesForCity(city) : [];
      closeSuggestions(localityInput, localityList);
    };
    const chooseCity = async (selected) => {
      cityInput.value = selected;
      await refreshLocalities(selected, true);
    };
    const cityMatches = (query) => {
      const q = String(query || "").trim().toLocaleLowerCase();
      return availableCities.filter((city) => !q || city.toLocaleLowerCase().includes(q));
    };

    cityInput.addEventListener("focus", () => showSuggestions(cityInput, cityList, availableCities, chooseCity, ""));
    cityInput.addEventListener("input", () => {
      showSuggestions(cityInput, cityList, cityMatches(cityInput.value), chooseCity, cityInput.value);
      // If the user types the full canonical city, refresh its localities immediately.
      const exact = exactCityName(cityInput.value);
      if (exact) refreshLocalities(exact, false);
    });
    cityInput.addEventListener("keydown", async (event) => {
      const options = cityList?.querySelectorAll(".autocomplete-option") || [];
      if (event.key === "ArrowDown" && options.length) { event.preventDefault(); options[0].focus(); }
      if (event.key === "Escape") closeSuggestions(cityInput, cityList);
      if (event.key === "Enter") {
        const exact = exactCityName(cityInput.value);
        const first = !cityList?.hidden ? cityList?.querySelector(".autocomplete-option") : null;
        if (!exact && first) {
          event.preventDefault();
          await chooseCity(first.dataset.value || cityInput.value);
        } else if (exact) {
          cityInput.value = exact;
          await refreshLocalities(exact, false);
          closeSuggestions(cityInput, cityList);
        }
      }
    });
    cityInput.addEventListener("change", async () => {
      const exact = exactCityName(cityInput.value);
      if (exact) cityInput.value = exact;
      await refreshLocalities(exact || cityInput.value, true);
    });
    cityInput.addEventListener("blur", () => window.setTimeout(() => closeSuggestions(cityInput, cityList), 140));

    if (localityInput) {
      localityInput.addEventListener("focus", async () => {
        const city = exactCityName(cityInput.value) || cityInput.value.trim();
        apiLocalities = await getLocalitiesForCity(city);
        showSuggestions(localityInput, localityList, apiLocalities, (selected) => { localityInput.value = selected; }, localityInput.value);
      });
      localityInput.addEventListener("input", () => {
        showSuggestions(localityInput, localityList, apiLocalities, (selected) => { localityInput.value = selected; }, localityInput.value);
      });
      localityInput.addEventListener("keydown", (event) => {
        const options = localityList?.querySelectorAll(".autocomplete-option") || [];
        if (event.key === "ArrowDown" && options.length) { event.preventDefault(); options[0].focus(); }
        if (event.key === "Escape") closeSuggestions(localityInput, localityList);
        if (event.key === "Enter") {
          const first = !localityList?.hidden ? localityList?.querySelector(".autocomplete-option") : null;
          if (first && !apiLocalities.some((item) => item.toLocaleLowerCase() === localityInput.value.trim().toLocaleLowerCase())) {
            event.preventDefault();
            localityInput.value = first.dataset.value || localityInput.value;
          }
          closeSuggestions(localityInput, localityList);
        }
      });
      localityInput.addEventListener("blur", () => window.setTimeout(() => closeSuggestions(localityInput, localityList), 140));
    }
    document.addEventListener("click", (event) => {
      if (!event.target.closest("#filter-city") && !event.target.closest("#city-suggestions")) closeSuggestions(cityInput, cityList);
      if (!event.target.closest("#filter-locality") && !event.target.closest("#locality-suggestions")) closeSuggestions(localityInput, localityList);
    });
    await refreshLocalities(cityInput.value, false);
  }

  function setDashboardContentVisible(visible) {
    [".kpi-grid", ".middle-grid", ".bottom-grid", ".market-insights-grid"].forEach((selector) => {
      $$(selector).forEach((node) => { node.hidden = !visible; node.style.display = visible ? "" : "none"; });
    });
  }

  async function loadMarket() {
    const city = $("#filter-city")?.value.trim() || "";
    const locality = $("#filter-locality")?.value.trim() || "";
    const bhk = $("#filter-bhk")?.value || "";

    if (requestController) requestController.abort();
    requestController = new AbortController();
    setLoading(true);
    show("#market-error", false);
    show("#market-results", true);
    setDashboardContentVisible(false);

    const params = new URLSearchParams();
    if (city) params.set("city", city);
    if (locality) params.set("locality", locality);
    if (bhk) params.set("bhk", bhk);

    try {
      const response = await fetch(`/api/market?${params.toString()}`, {
        credentials: "same-origin",
        cache: "no-store",
        signal: requestController.signal
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || "Market data could not be loaded.");
      if (!data.total_properties) {
        throw new Error("No matching properties were found. Try another city, locality or BHK selection.");
      }
      currentData = data;
      renderMarket(data);
      setDashboardContentVisible(true);
      show("#market-results", true);
    } catch (error) {
      if (error.name === "AbortError") return;
      currentData = null;
      setDashboardContentVisible(false);
      show("#market-results", true);
      show("#market-error", true);
      const message = error.message || "Unable to load live market data. Please try again.";
      // Never leave the previous city's KPIs in the hero after a failed city request.
      const requestedCity = $("#filter-city")?.value.trim() || "All Cities";
      setText("#hero-city-label", requestedCity);
      setText("#hero-property-count", "No matching records");
      const subtitle = $(".hero-subtitle");
      if (subtitle) subtitle.textContent = message;
      setText("#market-error-message", message);
    } finally {
      setLoading(false);
    }
  }

  function renderMarket(data) {
    // Header/hero: all values are sourced from the API response.
    setText("#hero-city-label", data.city || "All Cities");
    setText("#hero-property-count", `${fmtInt(data.total_properties)} indexed properties`);
    setText("#counter-properties", fmtInt(data.total_properties));
    setText("#counter-price", data.median_price_formatted || "—");
    setText("#counter-psf", number(data.median_ppsf) > 0 ? fmtInt(data.median_ppsf) : "—");
    setText("#counter-area", (data.median_area_formatted || "—").replace(/\s*sqft/i, "").trim());

    const areaSuffix = $("#counter-area")?.parentElement?.querySelector("span:last-child");
    if (areaSuffix && data.median_area_formatted && /sqft/i.test(data.median_area_formatted)) areaSuffix.textContent = "sqft";
    setText("#price-range-median-price", data.median_price_formatted || "—");
    setText("#price-range-median-ppsf", `with a median ${data.median_ppsf_formatted || "—"}`);

    const parsedQuantiles = parseP25P75(data);
    const quantiles = { p25: number(data.p25_ppsf) || parsedQuantiles.p25, p75: number(data.p75_ppsf) || parsedQuantiles.p75 };
    const rangeValues = [
      ["#ppsf-min", data.min_ppsf], ["#ppsf-p25", quantiles.p25],
      ["#ppsf-p75", quantiles.p75], ["#ppsf-max", data.max_ppsf]
    ];
    rangeValues.forEach(([selector, value]) => setText(selector, number(value) > 0 ? money(value) : "—"));

    const locationTitle = $("#hero-heading");
    if (locationTitle) locationTitle.setAttribute("aria-label", `Market analysis for ${data.city || "selected city"}`);
    const description = $(".hero-subtitle");
    if (description) description.textContent = `${fmtInt(data.total_properties)} indexed properties · Asking-price evidence, ₹/sqft patterns, BHK comparisons and locality-level context for ${data.locality && data.locality !== "All Localities" ? data.locality + ", " : ""}${data.city}.`;

    renderPriceRange(data, quantiles);
    renderBhk(data.bhk_distribution || []);
    renderLocalities(data.top_localities || []);
    renderDistribution(data.price_distribution || [], data.total_properties);
    renderInsights(data, quantiles);
  }

  function renderPriceRange(data, quantiles) {
    const wrap = $("#price-range-chart-wrap") || $(".density-chart-wrap");
    if (!wrap) return;

    // Keep each statistic on its own horizontal line. A log scale prevents an
    // extreme maximum from compressing Min/P25/Median/P75 into the same pixel.
    const points = [
      { label: "Minimum", value: number(data.min_ppsf), color: "#3478e5" },
      { label: "P25", value: number(data.p25_ppsf || quantiles.p25), color: "#3478e5" },
      { label: "Median", value: number(data.median_ppsf), color: "#d88c0c" },
      { label: "P75", value: number(data.p75_ppsf || quantiles.p75), color: "#3478e5" },
      { label: "Maximum", value: number(data.max_ppsf), color: "#e65b69" }
    ].filter((point) => Number.isFinite(point.value) && point.value > 0);

    if (!points.length) {
      wrap.innerHTML = '<div class="market-data-empty">Price-per-square-foot data is unavailable for this selection.</div>';
      return;
    }

    const observedMin = Math.min(...points.map((point) => point.value));
    const observedMax = Math.max(...points.map((point) => point.value));
    const domainMin = Math.max(1, observedMin / 1.5);
    const domainMax = Math.max(domainMin * 10, observedMax * 1.18);
    const logMin = Math.log10(domainMin);
    const logSpan = Math.log10(domainMax) - logMin || 1;

    const width = 620;
    const plotLeft = 82;
    const plotRight = 474;
    const plotWidth = plotRight - plotLeft;
    const x = (value) => plotLeft + ((Math.log10(Math.max(domainMin, Math.min(domainMax, value))) - logMin) / logSpan) * plotWidth;
    const rowStart = 29;
    const rowGap = 29;
    const axisY = 179;

    const compactTick = (value) => {
      if (value >= 1e7) return `${Number((value / 1e7).toFixed(value % 1e7 === 0 ? 0 : 1))}Cr`;
      if (value >= 1e5) return `${Number((value / 1e5).toFixed(value % 1e5 === 0 ? 0 : 1))}L`;
      if (value >= 1e3) return `${Number((value / 1e3).toFixed(value % 1e3 === 0 ? 0 : 1))}K`;
      return String(Math.round(value));
    };

    // Candidate ticks use 1/2/5 within each decade. Keep only ticks far enough
    // apart to make the labels readable at normal desktop and mobile widths.
    const candidates = [];
    const firstPower = Math.floor(Math.log10(domainMin));
    const lastPower = Math.ceil(Math.log10(domainMax));
    for (let power = firstPower; power <= lastPower; power += 1) {
      for (const multiplier of [1, 2, 5]) {
        const value = multiplier * Math.pow(10, power);
        if (value >= domainMin && value <= domainMax) candidates.push(value);
      }
    }
    const ticks = [];
    for (const value of candidates) {
      const px = x(value);
      if (!ticks.length || px - x(ticks[ticks.length - 1]) >= 52) ticks.push(value);
    }
    // Always show a right-end reference tick if there is room, without duplicating a nearby tick.
    const lastTick = candidates[candidates.length - 1];
    if (lastTick && (!ticks.length || x(lastTick) - x(ticks[ticks.length - 1]) >= 42)) ticks.push(lastTick);

    const grid = ticks.map((tick) => {
      const tx = x(tick);
      return `<line x1="${tx.toFixed(2)}" x2="${tx.toFixed(2)}" y1="15" y2="${axisY}" stroke="var(--chart-grid, #31465f)" stroke-opacity=".75" stroke-dasharray="2 3"/><text x="${tx.toFixed(2)}" y="198" text-anchor="middle" font-size="10.5" fill="var(--chart-label, #9db2ca)">${compactTick(tick)}</text>`;
    }).join("");

    const rows = points.map((point, index) => {
      const cy = rowStart + index * rowGap;
      const px = x(point.value);
      const valueLabel = money(point.value);
      return `<text x="6" y="${cy + 4}" font-size="11.5" font-weight="600" fill="var(--chart-label, #b9c9dd)">${point.label}</text>` +
        `<line x1="${plotLeft}" x2="${plotRight}" y1="${cy}" y2="${cy}" stroke="var(--chart-grid, #31465f)" stroke-width="5" stroke-linecap="round" stroke-opacity=".72"/>` +
        `<line x1="${plotLeft}" x2="${px.toFixed(2)}" y1="${cy}" y2="${cy}" stroke="${point.color}" stroke-width="5" stroke-linecap="round" stroke-opacity=".88"/>` +
        `<circle cx="${px.toFixed(2)}" cy="${cy}" r="5.1" fill="${point.color}" stroke="var(--donut-center, #0b1b2d)" stroke-width="1.6"/>` +
        `<text x="612" y="${cy + 4}" text-anchor="end" font-size="11.5" font-weight="700" fill="${point.color}">${valueLabel}</text>`;
    }).join("");

    wrap.innerHTML = `<svg class="live-range-svg" viewBox="0 0 ${width} 224" role="img" aria-label="Price per square foot statistics on a logarithmic scale. Each horizontal line shows the live minimum, 25th percentile, median, 75th percentile, and maximum." preserveAspectRatio="xMidYMid meet"><defs><linearGradient id="live-range-band" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#8dbdff"/><stop offset="50%" stop-color="#f5c65d"/><stop offset="100%" stop-color="#e8a4aa"/></linearGradient></defs>${grid}${rows}<line x1="${plotLeft}" x2="${plotRight}" y1="${axisY}" y2="${axisY}" stroke="var(--chart-grid, #64748b)" stroke-width="1"/><text x="${(plotLeft + plotRight) / 2}" y="221" text-anchor="middle" font-size="10.5" fill="var(--chart-label, #9db2ca)">Price per sq.ft. (₹) · logarithmic scale · live filtered records</text></svg>`;
  }

  function renderBhk(rows) {
    const table = $(".bhk-table");
    if (!table) return;
    const header = table.querySelector(".bhk-row.header");
    const maxPsf = Math.max(1, ...rows.map((row) => number(row.median_ppsf)));
    const markup = rows.length ? rows.map((row) => {
      const bhk = Number(row.bhk);
      const psf = number(row.median_ppsf);
      const width = Math.max(2, Math.min(100, psf / maxPsf * 100));
      return `<div class="bhk-row" role="row" data-bhk="${bhk} BHK"><span style="font-weight:600">${esc(row.label || `${bhk} BHK`)}</span><span>${fmtInt(row.count)}</span><span>${esc(row.median_price_formatted || formatCr(row.median_price))}</span><span>${psf ? money(psf) : "—"}</span><span style="padding-left:4px"><span class="range-bar-track"><span class="range-bar-fill ${bhk >= 4 ? "slate" : "blue"}" style="left:0;width:${width}%"></span><span class="range-bar-dot end" style="left:${width}%"></span></span></span></div>`;
    }).join("") : '<div class="market-data-empty">No BHK breakdown is available for this selection.</div>';
    table.innerHTML = (header ? header.outerHTML : '<div class="bhk-row header"><span>BHK</span><span>Count</span><span>Median Price</span><span>₹/sqft</span><span>Price range</span></div>') + markup + `<div class="bhk-axis-row" aria-hidden="true"><span></span><span></span><span></span><span></span><span class="bhk-axis-labels"><span>0</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></span></div>`;
    applyBhkHighlight();
  }

  function applyBhkHighlight() {
    const value = $("#bhk-select")?.value || "All BHK";
    $$(".bhk-row[data-bhk]").forEach((row) => row.classList.toggle("is-selected", value !== "All BHK" && row.dataset.bhk === value));
  }

  function renderLocalities(rows) {
    const container = $("#locality-rows-container");
    if (!container) return;
    const filtered = rows.filter((row) => number(row.count) > 0 && number(row.median_ppsf) >= 0 && number(row.median_ppsf) <= maxLocalityPsf);
    filtered.sort((a, b) => localitySort === "listings"
      ? number(b.count) - number(a.count) || number(b.median_ppsf) - number(a.median_ppsf)
      : number(b.median_ppsf) - number(a.median_ppsf) || number(b.count) - number(a.count));
    const maxCount = Math.max(1, ...filtered.map((row) => number(row.count)));
    const maxPsf = Math.max(1, ...filtered.map((row) => number(row.median_ppsf)));
    if (!filtered.length) {
      container.innerHTML = '<div class="market-data-empty">No locality records match the current view.</div>';
      return;
    }
    container.innerHTML = filtered.slice(0, 8).map((row, index) => {
      const count = number(row.count);
      const psf = number(row.median_ppsf);
      const width = localitySort === "listings" ? count / maxCount * 100 : psf / maxPsf * 100;
      return `<div class="locality-row live-locality" role="row"><span class="rank-badge">${index + 1}</span><strong class="locality-name">${esc(row.locality)}</strong><span class="locality-bar-track"><span class="locality-bar-fill" style="display:block;width:${width}%"></span></span><span>${fmtInt(count)}</span><span>${money(psf)}</span></div>`;
    }).join("");
    const slider = $("#locality-price-slider");
    const prices = rows.map((row) => number(row.median_ppsf)).filter((value) => value > 0);
    if (slider && prices.length) {
      const min = Math.floor(Math.min(...prices) / 1000) * 1000;
      const max = Math.ceil(Math.max(...prices) / 1000) * 1000;
      slider.min = String(min);
      slider.max = String(Math.max(max, min + 1000));
      slider.step = "100";
      if (!Number.isFinite(maxLocalityPsf) || maxLocalityPsf === Infinity) maxLocalityPsf = Number(slider.max);
      slider.value = String(Math.min(Number(slider.max), maxLocalityPsf));
      setText("#locality-price-value", money(slider.value));
    }
  }

  function renderDistribution(rows, totalProperties) {
    const donutWrap = $(".donut-wrap");
    const legend = $(".distribution-legend .legend-table");
    if (!donutWrap || !legend) return;
    const usable = (Array.isArray(rows) ? rows : []).map((row) => ({
      ...row,
      count: Math.max(0, Math.round(number(row.count))),
      range: String(row.range || "Price band")
    })).filter((row) => row.count > 0);
    const total = usable.reduce((sum, row) => sum + row.count, 0);
    if (!usable.length || !total) {
      donutWrap.innerHTML = '<div class="market-data-empty">Price distribution is unavailable.</div>';
      legend.innerHTML = '<div class="market-data-empty">No priced listings to distribute.</div>';
      return;
    }

    // Every segment is generated from the current API counts and ranges. No fixed
    // six-segment geometry or hard-coded percentages remain in the rendered chart.
    const radius = 65.5;
    const circumference = 2 * Math.PI * radius;
    const gap = Math.min(2.4, circumference / usable.length * 0.14);
    let offset = 0;
    const segments = usable.map((row, index) => {
      const share = row.count / total;
      const arc = share * circumference;
      const visibleArc = Math.max(0.8, arc - gap);
      const color = colors[index % colors.length];
      const segment = `<circle class="live-donut-segment" data-index="${index}" cx="150" cy="108" r="${radius}" fill="none" stroke="${color}" stroke-width="31" stroke-linecap="butt" stroke-dasharray="${visibleArc} ${Math.max(0, circumference - visibleArc)}" stroke-dashoffset="${-offset}" tabindex="0" role="img" aria-label="${esc(cleanRange(row.range))}: ${fmtInt(row.count)} listings, ${(share * 100).toFixed(1)} percent"/>`;
      offset += arc;
      return segment;
    }).join("");
    donutWrap.innerHTML = `<svg class="donut-svg" viewBox="0 0 300 216" role="img" aria-label="Distribution of ${fmtInt(total)} priced properties across ${usable.length} adaptive price bands"><g transform="rotate(-90 150 108)" style="filter:drop-shadow(0 5px 9px rgba(34,48,110,.16))">${segments}</g><circle cx="150" cy="108" r="46" fill="var(--donut-center, #fff)"/><text x="150" y="105" text-anchor="middle" font-size="22" font-weight="700" fill="var(--color-ink, #0f172a)" font-family="var(--font-serif, Georgia, serif)" id="donut-center-val">${fmtInt(total)}</text><text x="150" y="124" text-anchor="middle" font-size="11" fill="var(--color-muted, #64748b)" id="donut-center-sub">Priced listings</text></svg>`;
    legend.innerHTML = `<div class="legend-row header" role="row"><span role="columnheader" style="padding-left:28px">Adaptive price range</span><span role="columnheader" style="text-align:center">Listings</span><span role="columnheader" style="text-align:right">Share</span></div>` + usable.map((row, index) => {
      const share = row.count / total * 100;
      const color = colors[index % colors.length];
      return `<div class="legend-row" role="row" data-index="${index}" tabindex="0"><span><span class="color-dot" style="background:${color}"></span>${esc(cleanRange(row.range))}</span><span style="text-align:center">${fmtInt(row.count)}</span><span class="distribution-share" style="text-align:right;font-weight:600">${share.toFixed(1)}%</span></div>`;
    }).join("");
    $$(".legend-row[data-index]").forEach((row) => {
      const idx = Number(row.dataset.index);
      row.addEventListener("mouseenter", () => highlightDistribution(idx, usable));
      row.addEventListener("mouseleave", () => highlightDistribution(null, usable));
      row.addEventListener("focus", () => highlightDistribution(idx, usable));
      row.addEventListener("blur", () => highlightDistribution(null, usable));
    });
    $$(".live-donut-segment").forEach((segment) => {
      const idx = Number(segment.dataset.index);
      segment.addEventListener("mouseenter", () => highlightDistribution(idx, usable));
      segment.addEventListener("mouseleave", () => highlightDistribution(null, usable));
      segment.addEventListener("focus", () => highlightDistribution(idx, usable));
      segment.addEventListener("blur", () => highlightDistribution(null, usable));
    });
    setText("#donut-center-val", fmtInt(total));
    setText("#donut-center-sub", "Priced listings");
  }

  function cleanRange(range) {
    return String(range || "Price band").replace(/\s*Cr\s*$/i, "").replace(/₹/g, "₹");
  }

  function highlightDistribution(index, rows) {
    const total = rows.reduce((sum, row) => sum + number(row.count), 0);
    const segments = $$(".live-donut-segment");
    const legends = $$(".legend-row[data-index]");
    segments.forEach((segment, i) => {
      segment.style.opacity = index === null || i === index ? "1" : ".42";
      segment.style.transformOrigin = "150px 108px";
      segment.style.transform = index === i ? "scale(1.035)" : "scale(1)";
    });
    legends.forEach((row, i) => row.classList.toggle("active", index === i));
    if (index === null) {
      setText("#donut-center-val", fmtInt(total));
      setText("#donut-center-sub", "Priced listings");
    } else if (rows[index]) {
      setText("#donut-center-val", fmtInt(rows[index].count));
      setText("#donut-center-sub", `${(number(rows[index].count) / Math.max(1, total) * 100).toFixed(1)}% of listings`);
    }
  }

  function renderInsights(data, quantiles) {
    const bhk = (data.bhk_distribution || []).slice().sort((a, b) => number(b.count) - number(a.count));
    if (bhk.length) {
      const first = bhk[0];
      const second = bhk[1];
      setText("#bhk-note-title", "BHK evidence from current listings");
      setText("#bhk-note-body", second
        ? `${first.label} has the most matching listings (${fmtInt(first.count)}), followed by ${second.label} (${fmtInt(second.count)}). Median asking prices are ${first.median_price_formatted || formatCr(first.median_price)} and ${second.median_price_formatted || formatCr(second.median_price)} respectively.`
        : `${first.label} has ${fmtInt(first.count)} matching listings with a median asking price of ${first.median_price_formatted || formatCr(first.median_price)}.`);
    } else {
      setText("#bhk-note-title", "BHK evidence");
      setText("#bhk-note-body", "No BHK breakdown is available for the current selection.");
    }
    const locs = data.top_localities || [];
    const highest = locs.slice().sort((a, b) => number(b.median_ppsf) - number(a.median_ppsf))[0];
    setText("#market-size-insight-title", "Market coverage");
    setText("#market-size-insight-body", highest
      ? `${locs.length} localities are available for comparison. ${highest.locality} has the highest median among the localities returned (${money(highest.median_ppsf)}/sqft).`
      : "Locality-level comparison is not available for this selection.");
    const median = number(data.median_ppsf);
    setText("#hero-property-count", `${fmtInt(data.total_properties)} indexed properties`);
    if (median && quantiles.p25 && quantiles.p75) {
      const spread = quantiles.p75 - quantiles.p25;
      const note = $ ("#price-insight-body");
      if (note) note.textContent = `The middle half of listed properties falls between ${money(quantiles.p25)} and ${money(quantiles.p75)} per sq.ft.; the median is ${money(median)} per sq.ft.`;
    }
  }

  function wireInteractions() {
    $("#filter-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const cityInput = $("#filter-city");
      if (cityInput && cityInput.value.trim()) {
        const exact = exactCityName(cityInput.value);
        if (!exact) {
          show("#market-results", true);
          setDashboardContentVisible(false);
          show("#market-error", true);
          setText("#market-error-message", `Choose a city from the suggestions. “${cityInput.value.trim()}” is not in the available city list.`);
          return;
        }
        cityInput.value = exact;
      }
      loadMarket();
    });
    $("#market-retry")?.addEventListener("click", loadMarket);
    $("#btn-reset")?.addEventListener("click", async () => {
      if ($("#filter-city")) $("#filter-city").value = "";
      if ($("#filter-locality")) $("#filter-locality").value = "";
      if ($("#filter-bhk")) $("#filter-bhk").value = "";
      if ($("#bhk-select")) $("#bhk-select").value = "All BHK";
      maxLocalityPsf = Infinity;
      localitySort = "psf";
      $("#tab-psf")?.classList.add("active");
      $("#tab-listings")?.classList.remove("active");
      apiLocalities = $("#filter-city")?.value ? await getLocalitiesForCity($("#filter-city").value) : [];
      loadMarket();
    });
    $("#bhk-select")?.addEventListener("change", applyBhkHighlight);
    $("#tab-listings")?.addEventListener("click", () => {
      localitySort = "listings";
      $("#tab-listings").classList.add("active");
      $("#tab-psf")?.classList.remove("active");
      if (currentData) renderLocalities(currentData.top_localities || []);
    });
    $("#tab-psf")?.addEventListener("click", () => {
      localitySort = "psf";
      $("#tab-psf").classList.add("active");
      $("#tab-listings")?.classList.remove("active");
      if (currentData) renderLocalities(currentData.top_localities || []);
    });
    $("#locality-price-slider")?.addEventListener("input", (event) => {
      maxLocalityPsf = number(event.target.value);
      setText("#locality-price-value", money(maxLocalityPsf));
      if (currentData) renderLocalities(currentData.top_localities || []);
    });
    const themeToggle = $("#theme-toggle");
    const storageKey = "market-analyzer-theme";
    const applyTheme = (theme) => {
      document.documentElement.classList.toggle("dark", theme === "dark");
      if (themeToggle) {
        const next = theme === "dark" ? "light" : "dark";
        themeToggle.setAttribute("aria-label", `Switch to ${next} mode`);
        themeToggle.setAttribute("title", `Switch to ${next} mode`);
      }
    };
    let theme = "light";
    try { theme = localStorage.getItem(storageKey) || "light"; } catch (_) {}
    applyTheme(theme);
    themeToggle?.addEventListener("click", () => {
      const next = document.documentElement.classList.contains("dark") ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem(storageKey, next); } catch (_) {}
    });
    const menuToggle = $("#mobile-menu-toggle");
    const mobileMenu = $("#mobile-dropdown");
    menuToggle?.addEventListener("click", () => {
      const open = mobileMenu?.classList.toggle("open") || false;
      menuToggle.setAttribute("aria-expanded", String(open));
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    wireInteractions();
    try {
      const authResponse = await fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" });
      const auth = await authResponse.json();
      if (!auth.authenticated) {
        window.location.replace("/");
        return;
      }
    } catch (_) {
      window.location.replace("/");
      return;
    }
    await loadOptions();
    await loadMarket();
    $$(".draw-path").forEach((path) => path.classList.add("drawn"));
    $$(".fade-in").forEach((node) => node.classList.add("shown"));
  });
})();
