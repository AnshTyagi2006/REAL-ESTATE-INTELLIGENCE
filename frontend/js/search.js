(function () {
  "use strict";
  const $ = (s, root=document) => root.querySelector(s);
  const $$ = (s, root=document) => Array.from(root.querySelectorAll(s));
  const state = {
    city: "Gurgaon", maxPrice: 0, bhk: "", propertyType: "", types: new Set(),
    minArea: "", maxArea: "", sort: "default", page: 1, pageSize: 12,
    total: 0, totalPages: 1, shortlisted: new Set(), lastSearchKey: "", locality: ""
  };
  const esc = v => String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
  const num = v => { if (v == null || v === "") return null; const n = Number(String(v).replace(/[₹,%\s,]/g,"")); return Number.isFinite(n) ? n : null; };
  const money = v => { const n=Number(v); if(!Number.isFinite(n)||n<=0)return "Price on Request"; if(n>=1e7)return `₹${(n/1e7).toFixed(2)} Cr`; if(n>=1e5)return `₹${(n/1e5).toFixed(2)} L`; return `₹${Math.round(n).toLocaleString("en-IN")}`; };
  async function api(url, options={}) { const r=await fetch(url,{credentials:"same-origin",cache:"no-store",...options}); const d=await r.json().catch(()=>({})); if(!r.ok||d.success===false) throw new Error(d.error||`Request failed (${r.status})`); return d; }
  function toast(message){let el=$("#rei-toast");if(!el){el=document.createElement("div");el.id="rei-toast";el.className="toast";document.body.appendChild(el)}el.textContent=message;el.classList.add("show");clearTimeout(el._timer);el._timer=setTimeout(()=>el.classList.remove("show"),2500)}
  function setTheme(theme){const t=theme==="dark"?"dark":"light";document.documentElement.dataset.theme=t;try{localStorage.setItem("rei-search-theme",t);localStorage.setItem("theme",t)}catch{}const b=$("#themeToggle");if(b){b.setAttribute("aria-label",t==="dark"?"Switch to light theme":"Switch to dark theme");b.title=t==="dark"?"Switch to light theme":"Switch to dark theme"}}
  function initTheme(){let theme="light";try{theme=localStorage.getItem("rei-search-theme")||localStorage.getItem("theme")||"light"}catch{}setTheme(theme);$("#themeToggle")?.addEventListener("click",()=>setTheme(document.documentElement.dataset.theme==="dark"?"light":"dark"))}
  function mapProperty(p){const asking=num(p.asking_price_inr ?? p.price_inr);const predicted=num(p.predicted_value_inr ?? p.final_estimated_value ?? p.predicted_valuation_inr ?? p.estimated_value_inr);let diff=null, direction="unavailable";if(asking>0&&predicted>0){diff=Math.abs((predicted-asking)/asking*100);direction=asking<predicted?"below":asking>predicted?"above":"equal"}else if(p.prediction_direction){direction=p.prediction_direction==="below_valuation"?"below":p.prediction_direction==="above_valuation"?"above":p.prediction_direction==="equal"?"equal":"unavailable";const pct=num(p.asking_vs_predicted_percent);if(pct!==null)diff=Math.abs(pct)}const area=p.valuation_area_sqft ?? p.area_sqft;return {...p,_id:String(p.property_id??p.id??""),_asking:asking,_predicted:predicted,_diff:diff,_direction:direction,_area:num(area)||0,_beds:num(p.bedrooms)||0,_pricePerSqft:num(p.price_per_sqft)||0,_title:p.title||p.property_name||p.locality||"Property",_locality:p.locality||"",_city:p.city||state.city,_areaLabel:p.area_formatted||((num(area)||0).toLocaleString("en-IN")+" sq.ft."),_priceLabel:p.price_formatted||money(asking)}}
  function stableHash(value) {
    let hash = 0;
    for (const ch of String(value || "")) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
    return Math.abs(hash);
  }

  function propertyLogoMarkup(property) {
    const name = String(property._title || "").toLowerCase();
    const key = String(property.logo || "").toLowerCase();
    const shapes = {
      tower: '<path d="M8 41V25M16 41V15M24 41V7M32 41V20M40 41V12M5 42h40"/>',
      ananda: '<path d="m5 41 19-34 20 34M13 29l11-7 12 8M22 17l5 11"/>',
      solera: '<path d="M24 42C12 34 13 20 17 12c7 7 9 16 7 30ZM24 42c12-8 11-22 7-30-7 7-9 16-7 30ZM24 42V8M24 29l-8-7M24 31l8-8"/>',
      park: '<circle cx="24" cy="25" r="17"/><path d="M35 12c5 7 5 17 1 23M13 36c-5-7-5-16-1-23"/>',
      stack: '<path d="m24 6 18 9-18 9-18-9 18-9ZM6 25l18 9 18-9M6 33l18 9 18-9"/>',
      green: '<path d="M24 42c-8-6-12-14-11-25 7 2 11 8 11 16 1-10 5-17 13-21 1 14-3 23-13 30Z"/><path d="M24 42V15"/>',
      m3m: '<path d="M5 40V9l19 20L43 9v31M5 9l19 20L43 9"/>',
      primus: '<path d="M8 41V25M16 41V15M24 41V7M32 41V20M40 41V12M5 42h40"/>'
    };
    let variant = key;
    if (!shapes[variant]) {
      if (/ananda|rof/.test(name)) variant = "ananda";
      else if (/solera/.test(name)) variant = "solera";
      else if (/park/.test(name)) variant = "park";
      else if (/ninex|rmg/.test(name)) variant = "stack";
      else if (/green|court/.test(name)) variant = "green";
      else if (/m3m/.test(name)) variant = "m3m";
      else if (/dlf|primus/.test(name)) variant = "primus";
      else variant = "tower";
    }
    const color = ["ananda","green","park"].includes(variant) ? "#1762A8" : "#D98500";
    return `<span class="property-logo logo-${variant}" aria-hidden="true"><svg viewBox="0 0 48 48" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${shapes[variant]}</svg></span>`;
  }

  function propertyFigureMarkup(seed) {
    const figures = [
      '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="M15 65V14l29-7 29 7v51M9 65h70M22 19l22-5 22 5M22 28h8m8-2h8m8 2h8M22 38h8m8-2h8m8 2h8M22 48h8m8-2h8m8 2h8M22 58h8m8-2h8m8 2h8M39 65V52h12v13"/></svg>',
      '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="m8 35 36-27 36 27M15 32v33h58V32M10 65h68M24 65V43h15v22m8-22h16v12H47zM48 56h15v9M19 37h50"/></svg>',
      '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="M9 65h70M15 65V28l18-13 18 13v37M51 65V36l13-9 12 9v29M19 33h8m-8 9h8m-8 9h8m11-18h7m-7 9h7m-7 9h7m10-9h7m-7 9h7m-7 9h7M30 65V54h8v11"/></svg>',
      '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="M12 65h64M18 19h52v46M13 19h62M23 26h12v12H23zm18 0h12v12H41zm18 0h5v12h-5zM23 43h12v12H23zm18 0h12v12H41zm18 0h5v12h-5zM32 65V58h24v7M27 19v-6h34v6M39 13V7h10v6"/></svg>'
    ];
    return figures[stableHash(seed) % figures.length];
  }

  function cardEdgeAccentStyle(seed) {
    const shades = ["#F59A00", "#E9A414", "#F8C65A"];
    const hash = stableHash(seed);
    const pct = (offset) => `${12 + ((hash + offset * 17) % 72)}%`;
    const len = (offset) => `${18 + ((hash + offset * 11) % 28)}px`;
    const shade = (offset) => shades[(hash + offset) % shades.length];
    return `--edge-top-x:${pct(1)};--edge-top-length:${len(1)};--edge-top-gold:${shade(1)};` +
      `--edge-right-y:${pct(2)};--edge-right-length:${len(2)};--edge-right-gold:${shade(2)};` +
      `--edge-bottom-x:${pct(3)};--edge-bottom-length:${len(3)};--edge-bottom-gold:${shade(0)};` +
      `--edge-left-y:${pct(4)};--edge-left-length:${len(4)};--edge-left-gold:${shade(2)};`;
  }

  function cardMarkup(raw,index){
    const p=mapProperty(raw), saved=state.shortlisted.has(p._id), favorable=p._direction==='below';
    const badge=p._direction==='below'?'Value Opportunity':p._direction==='above'?'Above Valuation':p._direction==='equal'?'Fair Value':'';
    const status=p._direction==='below'?'is-below-value':p._direction==='above'?'is-above-value':p._direction==='equal'?'is-at-value':'is-unavailable';
    const valuation=p._diff===null?'Valuation unavailable':`${p._diff.toFixed(1)}% ${favorable?'below predicted value':p._direction==='above'?'above predicted value':'at predicted value'}`;
    const title=esc(p._title), id=esc(p._id), url=`/property/${encodeURIComponent(p._id)}`;
    const arrow=favorable?'↑':p._direction==='above'?'↓':'';
    return `<article class="property-card reveal-on-scroll" data-property-id="${id}" style="transition-delay:${Math.min(index*55,220)}ms;${cardEdgeAccentStyle(p._id || p._title)}">
      <div class="property-card__brand-row">
        <span class="property-card__logo" aria-label="${title} logo">${propertyLogoMarkup(p)}</span>
        ${badge?`<span class="property-card__badge ${favorable?'property-card__badge--opportunity':p._direction==='equal'?'property-card__badge--fair':'property-card__badge--overpriced'}">${esc(badge)}</span>`:''}
        <button type="button" class="property-card__favorite ${saved?'is-active':''}" data-favorite="${id}" aria-pressed="${saved}" aria-label="${saved?'Remove':'Add'} ${title} ${saved?'from':'to'} saved properties">${saved?'♥':'♡'}</button>
      </div>
      <header class="property-card__header">
        <div class="property-card__identity">
          <h3 class="property-card__name" title="${title}"><a href="${url}">${title}</a></h3>
          <p class="property-card__locality">${esc([p._locality,p._city].filter(Boolean).join(', '))}</p>
        </div>
        <span class="property-card__figure" aria-hidden="true">${propertyFigureMarkup(p._id || p._title)}</span>
      </header>
      <div class="property-card__divider" aria-hidden="true"><span></span></div>
      <div class="property-card__valuation">
        <div class="property-card__price"><span class="property-card__price-label">Asking Price</span><strong class="property-card__asking-price">${esc(p._priceLabel)}</strong></div>
        <div class="property-card__price property-card__predicted-price"><span class="property-card__price-label">Predicted Price</span><strong class="property-card__asking-price">${p._predicted>0?esc(money(p._predicted)):'Unavailable'}</strong></div>
      </div>
      <div class="property-card__valuation-status">
        <strong class="property-card__percentage ${status}">${p._diff===null?'—':`${arrow?`<span class="valuation-arrow" aria-hidden="true">${arrow}</span>`:''}<span class="status-dot"></span>${p._diff.toFixed(1)}%`}</strong>
        <span class="property-card__difference-label">${esc(valuation)}</span>
      </div>
      <div class="property-card__specifications" aria-label="Property specifications">
        <span class="property-card__spec"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 18v-8m0 5h18v3M6 10V7h5a3 3 0 0 1 3 3M3 15h18"/></svg><span>${esc(p._beds||'—')} BHK</span></span>
        <span class="property-card__spec"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><path d="M14 17h6m-3-3v6"/></svg><span>${esc(p._areaLabel)}</span></span>
        <a class="property-card__open" href="${url}" aria-label="View property ${title}">→</a>
      </div>
    </article>`;
  }
    function renderEmpty(title,body){return `<div class="empty-state"><div class="empty-mark">⌂</div><h3>${esc(title)}</h3><p>${esc(body)}</p><button type="button" data-reset="true">Reset filters</button></div>`}
  function selectedAreaButtons(){ $$("#areaOptions button").forEach(b=>{const lo=b.dataset.areaMin||"",hi=b.dataset.areaMax||"";b.classList.toggle("selected",lo===state.minArea&&hi===state.maxArea);b.setAttribute("aria-pressed",String(lo===state.minArea&&hi===state.maxArea))}) }
  function renderTypes(){const types=["Apartment","Builder Floor","Villa","House","Plot / Land","Commercial"];const box=$("#typeOptions");if(!box)return;box.innerHTML=types.map(t=>`<label class="type-option"><input type="checkbox" value="${esc(t)}" ${state.types.has(t)?"checked":""}><span class="custom-checkbox" aria-hidden="true"></span><span>${esc(t)}</span></label>`).join("");box.querySelectorAll("input").forEach(input=>input.addEventListener("change",()=>{input.checked?state.types.add(input.value):state.types.delete(input.value);state.propertyType='';if($('#heroType'))$('#heroType').value='all';state.page=1;loadProperties(true)}))}
  function renderChips(){const box=$("#activeFilterChips");if(!box)return;const chips=[];if(state.city)chips.push(state.city);if(state.locality)chips.push(state.locality);if(state.maxPrice)chips.push(`Up to ${money(state.maxPrice)}`);if(state.bhk)chips.push(`${state.bhk}${state.bhk==="5"?"+":""} BHK`);if(state.propertyType)chips.push(state.propertyType);if(state.types.size)chips.push(...state.types);if(state.minArea||state.maxArea)chips.push(`${state.minArea||0}–${state.maxArea||"∞"} sq.ft.`);box.innerHTML=chips.map(c=>`<span class="filter-chip">${esc(c)}</span>`).join("")}
  function renderPagination(){const pages=$("#pageNumbers");if(!pages)return;const start=Math.max(1,state.page-2),end=Math.min(state.totalPages,start+4);pages.innerHTML=Array.from({length:Math.max(0,end-start+1)},(_,i)=>start+i).map(p=>`<button type="button" data-page="${p}" class="${p===state.page?'active':''}" ${p===state.page?'aria-current="page"':''}>${p}</button>`).join("");const prev=$("#prevPage"),next=$("#nextPage");if(prev)prev.disabled=state.page<=1;if(next)next.disabled=state.page>=state.totalPages}
  async function loadShortlist(){try{const d=await api('/api/user/activity');state.shortlisted=new Set((d.shortlisted||[]).map(p=>String(p.property_id)))}catch(e){console.warn('Could not load saved properties:',e.message)}}
  async function recordSearch(){const filters={city:state.city,locality:state.locality||'',bedrooms:state.bhk,property_type:state.propertyType||Array.from(state.types).join(","),max_price:state.maxPrice||"",min_area:state.minArea||"",max_area:state.maxArea||""};const query=[state.city].filter(Boolean).join(" · ")||"All markets";const key=JSON.stringify({query,filters});if(key===state.lastSearchKey)return;try{await api('/api/user/searches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,filters})});state.lastSearchKey=key;localStorage.setItem('rei_activity_version',String(Date.now()));window.dispatchEvent(new CustomEvent('rei:activity-updated'))}catch(e){if(e.message!=='Not authenticated')console.warn('Search history was not saved:',e.message)}}
  async function loadProperties(record=true){const grid=$("#propertyGrid");if(!grid)return;grid.innerHTML='<div class="loading-skeleton" style="height:250px;grid-column:1/-1"></div>';const params=new URLSearchParams({page:String(state.page),page_size:String(state.pageSize),sort:state.sort});if(state.city)params.set('city',state.city);if(state.locality)params.set('locality',state.locality);if(state.types.size>1)params.set('property_types',Array.from(state.types).join(','));if(state.bhk)params.set('bedrooms',state.bhk);if(state.propertyType)params.set('property_type',state.propertyType);else if(state.types.size===1)params.set('property_type',Array.from(state.types)[0]);if(state.maxPrice)params.set('max_price',String(state.maxPrice));if(state.minArea)params.set('min_area',state.minArea);if(state.maxArea)params.set('max_area',state.maxArea);try{const d=await api('/api/properties?'+params.toString());state.total=d.total||0;state.totalPages=d.total_pages||1;$("#resultCount").textContent=state.total.toLocaleString('en-IN')+' properties';$("#resultLocation").textContent='in '+(state.city||'all markets');grid.className='property-grid';grid.innerHTML=(d.properties||[]).length?(d.properties||[]).map(cardMarkup).join(''):renderEmpty('No properties match those filters','Try a wider budget or choose a different location to see more homes.');renderPagination();renderChips();selectedAreaButtons();$$('#bedroomOptions button').forEach(b=>{const active=b.dataset.bhk===state.bhk;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active))});$('#budgetMaxLabel').textContent=state.maxPrice?money(state.maxPrice):'Any budget';if(record)await recordSearch()}catch(e){console.error('Property search failed:',e);grid.className='';grid.innerHTML=renderEmpty('Unable to load properties','Please refresh the page or try again.');}}
  function syncLocation(city){const next=city||'';if(next!==state.city)state.locality='';state.city=next;$('#heroLocation').value=state.city;$('#sidebarLocation').value=state.city;state.page=1;loadProperties(true)}
  function resetFilters(){state.maxPrice=0;state.bhk='';state.propertyType='';state.types.clear();state.minArea='';state.maxArea='';state.sort='default';state.page=1;$('#heroBudget').value='any';$('#heroBhk').value='0';$('#heroType').value='all';$('#budgetRange').value='500';$('#sortBy').value='default';renderTypes();loadProperties(true)}
  function applyQuickSearch(){
    const cityInput=$('#heroLocation'), city=(cityInput?.value||'').trim();
    if(!city){cityInput?.setCustomValidity('Please choose a city before searching.');cityInput?.reportValidity();cityInput?.focus();return;}
    cityInput.setCustomValidity('');
    const selectedCity = cityKey(city);
    if (!selectedCity) { toast('Please choose a city from the suggestions'); cityInput.focus(); return; }
    state.city = selectedCity;
    cityInput.value = selectedCity;
    state.locality = ($('#heroLocality')?.value || '').trim();
    state.maxPrice=({under50:5000000,under100:10000000,under200:20000000,under500:50000000})[$('#heroBudget').value]||0;
    state.bhk=$('#heroBhk').value==='0'?'':$('#heroBhk').value;
    state.propertyType=$('#heroType').value==='all'?'':$('#heroType').value;
    state.types.clear();renderTypes();state.page=1;
    $('#sidebarLocation').value=state.city;
    $('#budgetRange').value=String(state.maxPrice?Math.min(500,Math.round(state.maxPrice/100000)):500);
    loadProperties(true);$('#properties').scrollIntoView({behavior:'smooth',block:'start'});
  }

  // city_localities.js exports window.CITY_LOCALITIES. Build a city-level index
  // because some cities (Bangalore, Mumbai and Kolkata) are split into regions.
  const RAW_CITY_LOCALITIES = window.CITY_LOCALITIES || window.CITY_LOCALITIES_DATA || {};
  const CITY_REGION_PARENT = {
    "Bangalore Central": "Bangalore", "Bangalore East": "Bangalore",
    "Bangalore North": "Bangalore", "Bangalore South": "Bangalore", "Bangalore West": "Bangalore",
    "Central Mumbai": "Mumbai", "Mumbai South": "Mumbai", "Western Mumbai": "Mumbai",
    "Kolkata Central": "Kolkata", "Kolkata East": "Kolkata",
    "Kolkata North": "Kolkata", "Kolkata South": "Kolkata"
  };
  const normalizePlace = value => String(value ?? "").trim().replace(/\s+/g, " ");
  const canonicalCity = key => CITY_REGION_PARENT[normalizePlace(key)] || normalizePlace(key);
  const CITY_LOCALITY_INDEX = Object.create(null);
  Object.entries(RAW_CITY_LOCALITIES).forEach(([groupName, values]) => {
    const city = canonicalCity(groupName);
    if (!city) return;
    if (!Array.isArray(CITY_LOCALITY_INDEX[city])) CITY_LOCALITY_INDEX[city] = [];
    if (Array.isArray(values)) CITY_LOCALITY_INDEX[city].push(...values.map(normalizePlace).filter(Boolean));
  });
  Object.keys(CITY_LOCALITY_INDEX).forEach(city => {
    const seen = new Set();
    CITY_LOCALITY_INDEX[city] = CITY_LOCALITY_INDEX[city].filter(value => {
      const key = value.toLocaleLowerCase("en-IN");
      if (seen.has(key)) return false;
      seen.add(key); return true;
    }).sort((a, b) => a.localeCompare(b, "en-IN"));
  });
  const AVAILABLE_CITIES = Object.keys(CITY_LOCALITY_INDEX).sort((a, b) => a.localeCompare(b, "en-IN"));
  const cityKey = value => {
    const target = normalizePlace(value).toLocaleLowerCase("en-IN");
    return AVAILABLE_CITIES.find(city => city.toLocaleLowerCase("en-IN") === target) || "";
  };

  function populateCities(selectedCity) {
    const cityInput = $("#heroLocation");
    const sidebar = $("#sidebarLocation");
    const menu = $("#citySuggestions");
    const selected = cityKey(selectedCity || state.city) || "";
    const render = (query = cityInput?.value || "") => {
      if (!cityInput || !menu) return;
      const q = normalizePlace(query).toLocaleLowerCase("en-IN");
      const matches = AVAILABLE_CITIES.filter(name => !q || name.toLocaleLowerCase("en-IN").includes(q))
        .sort((a, b) => {
          if (!q) return a.localeCompare(b, "en-IN");
          const ap = a.toLocaleLowerCase("en-IN").startsWith(q) ? 0 : 1;
          const bp = b.toLocaleLowerCase("en-IN").startsWith(q) ? 0 : 1;
          return ap - bp || a.localeCompare(b, "en-IN");
        }).slice(0, 12);
      menu.replaceChildren();
      if (!matches.length) {
        const item = document.createElement("li");
        item.className = "autocomplete-empty";
        item.textContent = "No matching cities in the locality dataset";
        menu.appendChild(item);
      } else matches.forEach(name => {
        const item = document.createElement("li");
        item.setAttribute("role", "option");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "autocomplete-option";
        button.dataset.cityChoice = name;
        button.textContent = name;
        item.appendChild(button);
        menu.appendChild(item);
      });
      menu.hidden = false;
      cityInput.setAttribute("aria-expanded", "true");
    };
    const closeMenu = () => {
      if (menu) menu.hidden = true;
      cityInput?.setAttribute("aria-expanded", "false");
    };
    if (cityInput && !cityInput.dataset.cityAutocompleteBound) {
      cityInput.dataset.cityAutocompleteBound = "true";
      cityInput.addEventListener("input", () => {
        // A typed-but-unselected city must not leave a stale locality selected.
        state.locality = "";
        const locality = $("#heroLocality");
        if (locality) { locality.value = ""; locality.disabled = true; locality.placeholder = "Select a city first"; }
        render(cityInput.value);
      });
      cityInput.addEventListener("focus", () => render(cityInput.value));
      cityInput.addEventListener("keydown", event => {
        if (event.key === "Escape") closeMenu();
        if (event.key === "ArrowDown" && menu && !menu.hidden) {
          event.preventDefault(); menu.querySelector("button")?.focus();
        }
        if (event.key === "Enter" && menu && !menu.hidden) {
          const first = menu.querySelector("[data-city-choice]");
          if (first) { event.preventDefault(); first.click(); }
        }
      });
      menu?.addEventListener("click", event => {
        const button = event.target.closest("[data-city-choice]");
        if (!button) return;
        cityInput.value = button.dataset.cityChoice;
        state.city = cityInput.value;
        state.locality = "";
        if (sidebar) sidebar.value = state.city;
        closeMenu();
        cityInput.dispatchEvent(new Event("change", { bubbles: true }));
      });
      document.addEventListener("click", event => {
        if (!event.target.closest("#cityAutocomplete")) closeMenu();
      });
    }
    if (cityInput) cityInput.value = selected;
    if (sidebar) {
      const current = cityKey(sidebar.value || selected);
      sidebar.replaceChildren();
      const all = document.createElement("option");
      all.value = ""; all.textContent = "All cities"; sidebar.appendChild(all);
      AVAILABLE_CITIES.forEach(name => {
        const option = document.createElement("option");
        option.value = name; option.textContent = name; sidebar.appendChild(option);
      });
      sidebar.value = current || selected || "";
    }
  }

  function initLocalityAutocomplete() {
    const input = $("#heroLocality"), menu = $("#localitySuggestions"), cityInput = $("#heroLocation");
    if (!input || !menu || !cityInput) return;
    let localities = [];
    const close = () => { menu.hidden = true; input.setAttribute("aria-expanded", "false"); };
    const load = cityValue => {
      const city = cityKey(cityValue);
      localities = city ? [...(CITY_LOCALITY_INDEX[city] || [])] : [];
      input.value = "";
      state.locality = "";
      input.disabled = !city;
      input.placeholder = !city ? "Select a city first" : "Any locality";
      close();
    };
    const show = () => {
      if (input.disabled) return;
      const q = normalizePlace(input.value).toLocaleLowerCase("en-IN");
      const matches = localities.filter(name => !q || name.toLocaleLowerCase("en-IN").includes(q))
        .sort((a, b) => {
          if (!q) return a.localeCompare(b, "en-IN");
          const ap = a.toLocaleLowerCase("en-IN").startsWith(q) ? 0 : 1;
          const bp = b.toLocaleLowerCase("en-IN").startsWith(q) ? 0 : 1;
          return ap - bp || a.localeCompare(b, "en-IN");
        }).slice(0, 12);
      menu.replaceChildren();
      if (!matches.length) {
        const item = document.createElement("li");
        item.className = "autocomplete-empty";
        item.textContent = "No matching localities";
        menu.appendChild(item);
      } else matches.forEach(name => {
        const item = document.createElement("li");
        item.setAttribute("role", "option");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "autocomplete-option";
        button.dataset.localityChoice = name;
        button.textContent = name;
        item.appendChild(button);
        menu.appendChild(item);
      });
      menu.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };
    if (!input.dataset.localityAutocompleteBound) {
      input.dataset.localityAutocompleteBound = "true";
      input.addEventListener("focus", show);
      input.addEventListener("input", () => { state.locality = input.value.trim(); show(); });
      input.addEventListener("keydown", event => {
        if (event.key === "Escape") close();
        if (event.key === "ArrowDown" && !menu.hidden) { event.preventDefault(); menu.querySelector("button")?.focus(); }
        if (event.key === "Enter" && !menu.hidden) {
          const first = menu.querySelector("[data-locality-choice]");
          if (first) { event.preventDefault(); first.click(); }
        }
      });
      menu.addEventListener("click", event => {
        const button = event.target.closest("[data-locality-choice]");
        if (!button) return;
        state.locality = button.dataset.localityChoice;
        input.value = state.locality;
        close();
      });
      cityInput.addEventListener("change", () => {
        const city = cityKey(cityInput.value);
        if (!city) {
          state.city = "";
          if ($("#sidebarLocation")) $("#sidebarLocation").value = "";
          load("");
          return;
        }
        state.city = city;
        cityInput.value = city;
        if ($("#sidebarLocation")) $("#sidebarLocation").value = city;
        load(city);
      });
      document.addEventListener("click", event => {
        if (!event.target.closest("#localityAutocomplete")) close();
      });
      document.addEventListener("keydown", event => { if (event.key === "Escape") close(); });
    }
    load(state.city);
  }

  function bindEvents(){ $('#quickSearch')?.addEventListener('submit',e=>{e.preventDefault();applyQuickSearch()});$('#sidebarLocation')?.addEventListener('change',e=>syncLocation(e.target.value));$('#heroLocation')?.addEventListener('change',e=>{state.city=e.target.value.trim();if($('#sidebarLocation'))$('#sidebarLocation').value=state.city;});$('#heroLocality')?.addEventListener('change',e=>{state.locality=e.target.value.trim();});$('#heroBudget')?.addEventListener('change',applyQuickSearch);$('#heroBhk')?.addEventListener('change',applyQuickSearch);$('#heroType')?.addEventListener('change',applyQuickSearch);$('#budgetRange')?.addEventListener('input',e=>{const lakh=Number(e.target.value);state.maxPrice=lakh>=500?0:lakh*100000;$('#budgetMaxLabel').textContent=lakh>=500?'500+ L':`${lakh} L`});$('#budgetRange')?.addEventListener('change',()=>{state.page=1;loadProperties(true)});$('#bedroomOptions')?.addEventListener('click',e=>{const b=e.target.closest('[data-bhk]');if(!b)return;state.bhk=state.bhk===b.dataset.bhk?'':b.dataset.bhk;$('#heroBhk').value=state.bhk||'0';state.page=1;loadProperties(true)});$('#areaOptions')?.addEventListener('click',e=>{const b=e.target.closest('[data-area-min]');if(!b)return;state.minArea=b.dataset.areaMin==='0'?'':b.dataset.areaMin;state.maxArea=b.dataset.areaMax||'';if(b.dataset.areaMin==='0'&&b.dataset.areaMax==='0'){state.minArea='';state.maxArea=''}state.page=1;loadProperties(true)});$('#sortBy')?.addEventListener('change',e=>{state.sort=({'recommended':'default','price-low':'price_asc','price-high':'price_desc','area-high':'area_desc','price-per-area-low':'ppsf_asc','value':'default'})[e.target.value]||'default';state.page=1;loadProperties(false)});$('#sidebarSubmit')?.addEventListener('click',()=>{state.city=$('#sidebarLocation').value;state.page=1;loadProperties(true);$('#properties').scrollIntoView({behavior:'smooth',block:'start'})});$('#resetFilters')?.addEventListener('click',resetFilters);$('#mobileFilterToggle')?.addEventListener('click',()=>{const panel=$('#filterPanel');const open=panel.classList.toggle('is-open');$('#mobileFilterToggle').setAttribute('aria-expanded',String(open));$('#mobileFilterToggle').textContent=open?'Hide filters':'Show filters'});$('#prevPage')?.addEventListener('click',()=>{if(state.page>1){state.page--;loadProperties(false)}});$('#nextPage')?.addEventListener('click',()=>{if(state.page<state.totalPages){state.page++;loadProperties(false)}});$('#pageNumbers')?.addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(!b)return;state.page=Number(b.dataset.page);loadProperties(false)});$('#propertyGrid')?.addEventListener('click',async e=>{const detail=e.target.closest('.property-card__open, .property-card__name a, a.details-button, .property-heading a');if(detail){const card=detail.closest('.property-card');const favId=card?.querySelector('[data-favorite]')?.dataset.favorite;if(favId){fetch('/api/user/recently-viewed',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({property_id:String(favId)})}).catch(()=>{});fetch('/api/user/activity-event',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_type:'property_click',page:location.pathname,property_id:String(favId)})}).catch(()=>{});}return;}const fav=e.target.closest('[data-favorite]');if(fav){e.preventDefault();const id=String(fav.dataset.favorite);if(!id)return;const adding=!state.shortlisted.has(id);fav.disabled=true;try{const d=await api('/api/user/shortlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({property_id:id,action:adding?'add':'remove'})});if(d.shortlisted){state.shortlisted.add(id);fav.classList.add('is-active');fav.classList.add('is-favorite');fav.textContent='♥';fav.setAttribute('aria-pressed','true');fav.setAttribute('aria-label','Remove from saved properties');toast('Property saved')}else{state.shortlisted.delete(id);fav.classList.remove('is-active');fav.classList.remove('is-favorite');fav.textContent='♡';fav.setAttribute('aria-pressed','false');fav.setAttribute('aria-label','Add to saved properties');toast('Property removed')}localStorage.setItem('rei_activity_version',String(Date.now()));window.dispatchEvent(new CustomEvent('rei:activity-updated'))}catch(err){toast(err.message==='Not authenticated'?'Please sign in to save properties':`Unable to update shortlist: ${err.message}`)}finally{fav.disabled=false}return}});$('#propertyGrid')?.addEventListener('click',e=>{const reset=e.target.closest('[data-reset]');if(reset)resetFilters()});}
  async function init(){initTheme();bindEvents();renderTypes();try{const auth=await api('/api/auth/me');if(!auth.authenticated){location.replace('/');return}}catch{location.replace('/');return}try{await loadShortlist()}catch{}const params=new URLSearchParams(location.search);state.city=cityKey(params.get('city')||'Gurgaon')||cityKey('Gurgaon')||AVAILABLE_CITIES[0]||'';state.locality=params.get('locality')||'';state.bhk=params.get('bedrooms')||params.get('bhk')||'';populateCities(state.city);$('#heroLocation').value=state.city;$('#sidebarLocation').value=state.city;$('#heroBhk').value=state.bhk||'0';initLocalityAutocomplete();$('#heroLocality').value=state.locality;await loadProperties(true);}
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',init):init();
})();
