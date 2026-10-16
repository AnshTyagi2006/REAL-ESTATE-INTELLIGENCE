(() => {
    'use strict';

    /* =========================================================
       CORE HELPERS
    ========================================================= */

    const $ = (selector, root = document) =>
        root.querySelector(selector);

    const $$ = (selector, root = document) =>
        Array.from(root.querySelectorAll(selector));

    const root = document.documentElement;
    const body = document.body;

    const reduceMotion =
        window.matchMedia(
            '(prefers-reduced-motion: reduce)'
        ).matches;

    let lenis = null;


    /* =========================================================
       EXISTING APPLICATION STATE
    ========================================================= */

    const auth = {
        authenticated: false,
        ready: Promise.resolve(false),
        redirectTo: '/home',
        lastFocused: null
    };

    const modal = $('#auth-overlay');
    const dialog = $('.auth-modal', modal);
    const message = $('#auth-message');

    const loginForm = $('#login-form');
    const registerForm = $('#register-form');

    const title = $('#auth-title');
    const subtitle = $('#auth-subtitle');

    const loginTab = $('#login-tab');
    const registerTab = $('#register-tab');

    const mobileMenu = $('#mobile-menu');
    const menuToggle = $('#menu-toggle');


    /* =========================================================
       CITY DATA
    ========================================================= */

    const cityCounts = {
        Bangalore: '1,041',
        Chandigarh: '1,683',
        Dehradun: '936',
        Delhi: '1,335',
        Faridabad: '603',
        Ghaziabad: '876',
        'Greater Noida': '94',
        Gurgaon: '1,009',
        Hyderabad: '1,376',
        Kolkata: '1,381',
        Mohali: '840',
        Mumbai: '1,023',
        Noida: '1,241',
        Panchkula: '323'
    };

    /* =========================================================
       FACTOR DATA
    ========================================================= */

    const factorDetails = {
        area: [
            'Area',
            '2,071 sqft · positive model influence in this conceptual example.'
        ],

        bedrooms: [
            'Bedrooms',
            '3 bedrooms · positive model influence in this conceptual example.'
        ],

        bathrooms: [
            'Bathrooms',
            'Available bathroom details · positive model influence in this conceptual example.'
        ],

        locality: [
            'Locality',
            'Locality-level market characteristics · downward model influence in this conceptual example.'
        ],

        location: [
            'Location',
            'Location-related market characteristics · downward model influence in this conceptual example.'
        ],

        floor: [
            'Floor features',
            'Available floor characteristics · downward model influence in this conceptual example.'
        ]
    };


    /* =========================================================
       STORAGE
    ========================================================= */

    function safeStorageGet(key) {
        try {
            return window.localStorage.getItem(key);
        } catch (_) {
            return null;
        }
    }


    function safeStorageSet(key, value) {
        try {
            window.localStorage.setItem(key, value);
        } catch (_) {
            /* Storage may be unavailable. */
        }
    }


    /* =========================================================
       THEME
    ========================================================= */

    function setTheme(theme) {

        const isDark =
            theme === 'dark';

        root.dataset.theme =
            isDark ? 'dark' : 'light';

        const toggle =
            $('[data-theme-toggle]');

        if (toggle) {

            toggle.setAttribute(
                'aria-pressed',
                String(isDark)
            );

            toggle.setAttribute(
                'aria-label',
                isDark
                    ? 'Switch to light theme'
                    : 'Switch to dark theme'
            );

            const icon =
                $('span', toggle);

            if (icon) {
                icon.textContent =
                    isDark ? '☼' : '◐';
            }
        }

        safeStorageSet(
            'rei-theme',
            isDark ? 'dark' : 'light'
        );
    }


    /* =========================================================
       AUTH UI
    ========================================================= */

    function updateAuthUI() {

        $$('[data-auth-open]')
            .forEach(control => {

                control.hidden =
                    auth.authenticated;

            });


        $$('[data-dashboard]')
            .forEach(link => {

                link.hidden =
                    !auth.authenticated;

            });


        const mobileWorkspace =
            $('.mobile-workspace');

        if (mobileWorkspace) {

            mobileWorkspace.textContent =
                auth.authenticated
                    ? 'Open dashboard ↗'
                    : 'Explore workspace ↗';

            mobileWorkspace.href =
                '/home';
        }
    }


    function checkAuthentication() {

        auth.ready =
            fetch(
                '/api/auth/me',
                {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        Accept:
                            'application/json'
                    }
                }
            )

            .then(async response => {

                if (!response.ok) {
                    return false;
                }

                const data =
                    await response
                        .json()
                        .catch(() => ({}));

                return Boolean(
                    data &&
                    (
                        data.user ||
                        data.authenticated === true ||
                        data.id ||
                        data.username ||
                        data.email
                    )
                );
            })

            .catch(() => false)

            .then(isAuthenticated => {

                auth.authenticated =
                    isAuthenticated;

                updateAuthUI();

                return isAuthenticated;
            });

        return auth.ready;
    }


    function setMode(mode) {

        const registering =
            mode === 'register';

        if (!loginForm || !registerForm) {
            return;
        }

        loginForm.hidden =
            registering;

        registerForm.hidden =
            !registering;


        loginTab?.classList.toggle(
            'active',
            !registering
        );

        registerTab?.classList.toggle(
            'active',
            registering
        );


        loginTab?.setAttribute(
            'aria-selected',
            String(!registering)
        );

        registerTab?.setAttribute(
            'aria-selected',
            String(registering)
        );


        if (title) {

            title.textContent =
                registering
                    ? 'Create your account'
                    : 'Welcome back';
        }


        if (subtitle) {

            subtitle.textContent =
                registering
                    ? 'Build a personal property research workspace.'
                    : 'Sign in to continue to your property intelligence workspace.';
        }


        const authSwitch =
            $('#auth-switch');

        const authSwitchRegister =
            $('#auth-switch-register');


        if (authSwitch) {
            authSwitch.hidden =
                registering;
        }

        if (authSwitchRegister) {
            authSwitchRegister.hidden =
                !registering;
        }


        if (message) {
            message.textContent = '';
            message.classList.remove(
                'success'
            );
        }


        if (registering) {

            $('#register-name')?.focus();

        } else {

            $('#login-email')?.focus();

        }
    }


    function openAuth(
        mode = 'login',
        destination = '/home'
    ) {

        if (!modal) {
            return;
        }

        auth.redirectTo =
            destination || '/home';

        auth.lastFocused =
            document.activeElement;

        closeMobileMenu();

        modal.hidden = false;

        body.classList.add(
            'modal-open'
        );

        setMode(mode);

        const authModal =
            $('.auth-modal', modal);

        authModal?.focus({
            preventScroll: true
        });


        const firstInput =
            mode === 'register'
                ? $('#register-name')
                : $('#login-email');


        window.setTimeout(
            () => {
                firstInput?.focus();
            },
            0
        );
    }


    function closeAuth() {

        if (
            !modal ||
            modal.hidden
        ) {
            return;
        }

        modal.hidden = true;

        body.classList.remove(
            'modal-open'
        );


        if (message) {

            message.textContent = '';

            message.classList.remove(
                'success'
            );
        }


        if (
            auth.lastFocused &&
            typeof auth.lastFocused.focus ===
                'function'
        ) {
            auth.lastFocused.focus();
        }
    }


    function closeMobileMenu() {

        if (
            !mobileMenu ||
            !menuToggle
        ) {
            return;
        }

        mobileMenu.hidden = true;

        menuToggle.setAttribute(
            'aria-expanded',
            'false'
        );

        menuToggle.setAttribute(
            'aria-label',
            'Open navigation menu'
        );
    }


    function setMessage(
        text,
        success = false
    ) {

        if (!message) {
            return;
        }

        message.textContent = text;

        message.classList.toggle(
            'success',
            success
        );
    }


    function formValues(form) {

        return Object.fromEntries(
            new FormData(form).entries()
        );
    }


    async function readError(response) {

        const data =
            await response
                .json()
                .catch(() => ({}));

        const detail =
            data.detail ||
            data.message ||
            data.error;


        if (Array.isArray(detail)) {

            return detail
                .map(
                    item =>
                        item.msg ||
                        item.message
                )
                .filter(Boolean)
                .join(' ');
        }


        return typeof detail === 'string'
            ? detail
            : '';
    }


    function friendlyAuthError(
        response,
        detail,
        mode
    ) {

        if (
            response.status === 401 ||
            response.status === 403
        ) {
            return 'Email or password is incorrect.';
        }


        if (response.status === 409) {

            return (
                detail ||
                'An account with this email already exists.'
            );
        }


        if (
            detail &&
            !/internal server error|traceback/i
                .test(detail)
        ) {
            return detail;
        }


        return mode === 'register'
            ? 'We couldn’t create your account. Please try again.'
            : 'We couldn’t sign you in. Please try again.';
    }


    async function submitAuth(
        form,
        mode
    ) {

        const values =
            formValues(form);

        const email =
            String(
                values.username || ''
            ).trim();

        const password =
            String(
                values.password || ''
            );


        const emailPattern =
            /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


        if (
            mode === 'register' &&
            !String(values.name || '').trim()
        ) {

            setMessage(
                'Please enter your full name.'
            );

            $('#register-name')?.focus();

            return;
        }


        if (
            !emailPattern.test(email)
        ) {

            setMessage(
                'Please enter a valid email.'
            );

            (
                mode === 'register'
                    ? $('#register-email')
                    : $('#login-email')
            )?.focus();

            return;
        }


        if (!password) {

            setMessage(
                'Please enter your password.'
            );

            (
                mode === 'register'
                    ? $('#register-password')
                    : $('#login-password')
            )?.focus();

            return;
        }


        if (
            mode === 'register' &&
            password.length < 8
        ) {

            setMessage(
                'Use at least 8 characters for your password.'
            );

            $('#register-password')?.focus();

            return;
        }


        if (
            mode === 'register' &&
            password !==
                values['confirm-password']
        ) {

            setMessage(
                'Your passwords do not match.'
            );

            $('#register-confirm')?.focus();

            return;
        }


        const submit =
            $('.auth-submit', form);

        if (!submit) {
            return;
        }


        const originalText =
            submit.innerHTML;

        submit.disabled = true;

        submit.textContent =
            mode === 'register'
                ? 'Creating account…'
                : 'Signing in…';

        setMessage('');


        const payload =
            mode === 'register'
                ? {
                    name:
                        String(
                            values.name
                        ).trim(),

                    username:
                        email,

                    password
                }

                : {
                    username:
                        email,

                    password
                };


        try {

            const response =
                await fetch(
                    `/api/auth/${mode}`,
                    {
                        method: 'POST',
                        credentials: 'include',

                        headers: {
                            'Content-Type':
                                'application/json',

                            Accept:
                                'application/json'
                        },

                        body:
                            JSON.stringify(
                                payload
                            )
                    }
                );


            if (!response.ok) {

                const detail =
                    await readError(
                        response
                    );

                setMessage(
                    friendlyAuthError(
                        response,
                        detail,
                        mode
                    )
                );

                return;
            }


            auth.authenticated =
                true;

            updateAuthUI();


            setMessage(
                mode === 'register'
                    ? 'Account created successfully.'
                    : 'Signed in successfully.',
                true
            );


            window.setTimeout(
                () => {

                    window.location.assign(
                        auth.redirectTo ||
                        '/home'
                    );

                },
                350
            );

        } catch (_) {

            setMessage(
                'Unable to reach the account service. Please try again.'
            );

        } finally {

            submit.disabled = false;

            submit.innerHTML =
                originalText;
        }
    }


    function navigateProtected(
        event,
        link
    ) {

        if (auth.authenticated) {
            return;
        }

        event.preventDefault();

        const destination =
            link.getAttribute('href') ||
            '/home';


        auth.ready.then(
            isAuthenticated => {

                if (isAuthenticated) {

                    window.location.assign(
                        destination
                    );

                } else {

                    openAuth(
                        'login',
                        destination
                    );
                }
            }
        );
    }


    /* =========================================================
       CITY SELECTOR
    ========================================================= */

    function initializeCitySelector() {

        const cityButtons =
            $$('.city-option');

        const selectedCity =
            $('#selected-city');

        const selectedCount =
            $('#selected-count');

        const marketLink =
            $('#market-search-link');

        const illustration =
            $('.market-architecture');

        const marketImage =
            $('#market-city-image');

        const updateMarketImage = (city, cityButton) => {
            const imagePath = cityButton?.dataset.imageSrc;
            const backdrop = $('.market-backdrop');

            if (!marketImage || !imagePath) {
                return;
            }

            marketImage.dataset.imagePath = imagePath;
            marketImage.alt = `Residential market in ${city}`;
            marketImage.hidden = false;
            backdrop?.classList.remove('image-unavailable');
            marketImage.onload = () => {
                if (marketImage.dataset.imagePath === imagePath) {
                    marketImage.hidden = false;
                    backdrop?.classList.remove('image-unavailable');
                }
            };
            marketImage.onerror = () => {
                if (marketImage.dataset.imagePath === imagePath) {
                    marketImage.hidden = true;
                    backdrop?.classList.add('image-unavailable');
                }
            };
            marketImage.src = imagePath;

            illustration?.setAttribute(
                'aria-label',
                `Residential market image for ${city}`
            );
        };

        const initialCityButton =
            $('.city-option.active') || cityButtons[0];
        updateMarketImage(
            initialCityButton?.dataset.city || 'Bangalore',
            initialCityButton
        );

        cityButtons.forEach(button => {

            button.addEventListener(
                'click',
                () => {

                    const city =
                        button.dataset.city;


                    cityButtons.forEach(
                        option => {

                            const selected =
                                option ===
                                button;

                            option.classList.toggle(
                                'active',
                                selected
                            );

                            option.setAttribute(
                                'aria-pressed',
                                String(selected)
                            );
                        }
                    );


                    if (selectedCity) {
                        selectedCity.textContent =
                            city;
                    }


                    if (selectedCount) {
                        selectedCount.textContent =
                            cityCounts[city] ||
                            '—';
                    }


                    if (marketLink) {

                        marketLink.href =
                            `/search?city=${encodeURIComponent(city)}`;

                        marketLink.setAttribute(
                            'aria-label',
                            `Explore ${city} properties`
                        );
                    }

                    updateMarketImage(city, button);

                    if (illustration) {

                        illustration.classList.add(
                            'is-changing'
                        );

                        window.setTimeout(
                            () => {

                                illustration.classList.remove(
                                    'is-changing'
                                );

                            },
                            420
                        );
                    }
                }
            );

        });
    }


    /* =========================================================
       FACTORS
    ========================================================= */

    function initializeFactors() {

        const factorButtons =
            $$('.factor-button');


        factorButtons.forEach(
            button => {

                button.addEventListener(
                    'click',
                    () => {

                        factorButtons.forEach(
                            factor => {

                                const active =
                                    factor ===
                                    button;

                                factor.classList.toggle(
                                    'active',
                                    active
                                );

                                factor.setAttribute(
                                    'aria-pressed',
                                    String(active)
                                );
                            }
                        );


                        const details =
                            factorDetails[
                                button.dataset.factor
                            ] ||
                            [
                                'Factor',
                                'Conceptual model influence.'
                            ];


                        const factorTitle =
                            $('#factor-title');

                        const factorDescription =
                            $('#factor-description');


                        if (factorTitle) {
                            factorTitle.textContent =
                                details[0];
                        }

                        if (factorDescription) {
                            factorDescription.textContent =
                                details[1];
                        }
                    }
                );
            }
        );
    }


    /* =========================================================
       EXISTING INTERACTIONS
    ========================================================= */

    function initializeInteractions() {

        const themeToggle =
            $('[data-theme-toggle]');


        themeToggle?.addEventListener(
            'click',
            () => {

                setTheme(
                    root.dataset.theme ===
                        'dark'
                        ? 'light'
                        : 'dark'
                );

            }
        );


        if (
            menuToggle &&
            mobileMenu
        ) {

            menuToggle.addEventListener(
                'click',
                () => {

                    const opening =
                        mobileMenu.hidden;

                    mobileMenu.hidden =
                        !opening;

                    menuToggle.setAttribute(
                        'aria-expanded',
                        String(opening)
                    );

                    menuToggle.setAttribute(
                        'aria-label',
                        opening
                            ? 'Close navigation menu'
                            : 'Open navigation menu'
                    );


                    if (
                        opening &&
                        !reduceMotion &&
                        window.gsap
                    ) {

                        gsap.fromTo(
                            mobileMenu,
                            {
                                opacity: 0,
                                y: -12
                            },
                            {
                                opacity: 1,
                                y: 0,
                                duration: .35,
                                ease:
                                    'power3.out'
                            }
                        );


                        gsap.fromTo(
                            $$('#mobile-menu > *'),
                            {
                                y: 15,
                                opacity: 0
                            },
                            {
                                y: 0,
                                opacity: 1,
                                duration: .4,
                                stagger: .05,
                                ease:
                                    'power3.out'
                            }
                        );
                    }
                }
            );
        }


        $$('[data-auth-open]')
            .forEach(button => {

                button.addEventListener(
                    'click',
                    () => {

                        openAuth(
                            button.dataset
                                .authOpen
                        );

                    }
                );
            });


        $$('[data-auth-mode]')
            .forEach(button => {

                button.addEventListener(
                    'click',
                    () => {

                        setMode(
                            button.dataset
                                .authMode
                        );

                    }
                );
            });


        $$('[data-protected-route]')
            .forEach(link => {

                link.addEventListener(
                    'click',
                    event => {

                        navigateProtected(
                            event,
                            link
                        );

                    }
                );
            });


        $$('.mobile-menu a[href^="#"]')
            .forEach(link => {

                link.addEventListener(
                    'click',
                    closeMobileMenu
                );

            });


        $('#auth-close')
            ?.addEventListener(
                'click',
                closeAuth
            );


        modal?.addEventListener(
            'click',
            event => {

                if (
                    event.target ===
                    modal
                ) {
                    closeAuth();
                }

            }
        );


        loginForm?.addEventListener(
            'submit',
            event => {

                event.preventDefault();

                submitAuth(
                    loginForm,
                    'login'
                );

            }
        );


        registerForm?.addEventListener(
            'submit',
            event => {

                event.preventDefault();

                submitAuth(
                    registerForm,
                    'register'
                );

            }
        );


        $$('[data-password-toggle]')
            .forEach(button => {

                button.addEventListener(
                    'click',
                    () => {

                        const input =
                            document.getElementById(
                                button.dataset
                                    .passwordToggle
                            );

                        if (!input) {
                            return;
                        }


                        const showing =
                            input.type ===
                            'password';


                        input.type =
                            showing
                                ? 'text'
                                : 'password';


                        button.textContent =
                            showing
                                ? 'Hide'
                                : 'Show';


                        button.setAttribute(
                            'aria-label',
                            `${
                                showing
                                    ? 'Hide'
                                    : 'Show'
                            } password`
                        );
                    }
                );
            });


        document.addEventListener(
            'keydown',
            event => {

                if (
                    event.key ===
                    'Escape'
                ) {

                    if (
                        modal &&
                        !modal.hidden
                    ) {
                        closeAuth();
                    } else {
                        closeMobileMenu();
                    }
                }


                if (
                    event.key === 'Tab' &&
                    modal &&
                    !modal.hidden &&
                    dialog
                ) {

                    const focusable =
                        $$(
                            'button:not([disabled]), input:not([disabled]), a[href]',
                            dialog
                        ).filter(
                            item =>
                                !item.closest(
                                    '[hidden]'
                                )
                        );


                    if (!focusable.length) {
                        return;
                    }


                    const first =
                        focusable[0];

                    const last =
                        focusable[
                            focusable.length - 1
                        ];


                    if (
                        event.shiftKey &&
                        document.activeElement ===
                            first
                    ) {

                        event.preventDefault();

                        last.focus();

                    } else if (
                        !event.shiftKey &&
                        document.activeElement ===
                            last
                    ) {

                        event.preventDefault();

                        first.focus();
                    }
                }
            }
        );


        const header =
            $('.site-header');

        let ticking = false;


        const updateHeader = () => {

            header?.classList.toggle(
                'is-scrolled',
                window.scrollY > 12
            );

            ticking = false;
        };


        window.addEventListener(
            'scroll',
            () => {

                if (!ticking) {

                    ticking = true;

                    window.requestAnimationFrame(
                        updateHeader
                    );
                }
            },
            {
                passive: true
            }
        );


        updateHeader();


        window.addEventListener(
            'resize',
            () => {

                if (
                    window.innerWidth >
                    900
                ) {
                    closeMobileMenu();
                }

            }
        );


        const year =
            $('#current-year');

        if (year) {

            year.textContent =
                String(
                    new Date()
                        .getFullYear()
                );
        }
    }


    /* =========================================================
       MOTION LIBRARIES
    ========================================================= */

    function initLibraries() {

        if (!window.gsap) {

            console.warn(
                'GSAP is required for the motion system.'
            );

            return false;
        }


        if (window.ScrollTrigger) {

            gsap.registerPlugin(
                ScrollTrigger
            );

        }


        if (
            !reduceMotion &&
            window.Lenis
        ) {

            lenis =
                new Lenis({
                    duration: 1.15,
                    smoothWheel: true,
                    smoothTouch: false,
                    wheelMultiplier: .9,
                    touchMultiplier: 1
                });


            lenis.on(
                'scroll',
                () => {

                    if (
                        window.ScrollTrigger
                    ) {
                        ScrollTrigger.update();
                    }
                }
            );


            gsap.ticker.add(
                time => {

                    lenis.raf(
                        time * 1000
                    );

                }
            );


            gsap.ticker.lagSmoothing(
                0
            );
        }


        return true;
    }


    /* =========================================================
       ANCHOR / SMOOTH SCROLL
    ========================================================= */

    function setupAnchorScrolling() {

        $$(
            'a[href^="#"]'
        ).forEach(link => {

            link.addEventListener(
                'click',
                event => {

                    const id =
                        link.getAttribute(
                            'href'
                        );


                    if (
                        !id ||
                        id === '#'
                    ) {
                        return;
                    }


                    const target =
                        $(id);


                    if (!target) {
                        return;
                    }


                    event.preventDefault();


                    if (lenis) {

                        lenis.scrollTo(
                            target,
                            {
                                offset: -90,
                                duration: 1.2
                            }
                        );

                    } else {

                        target.scrollIntoView({
                            behavior:
                                reduceMotion
                                    ? 'auto'
                                    : 'smooth'
                        });

                    }
                }
            );
        });
    }


    /* =========================================================
       CURSOR GLOW
    ========================================================= */

    function setupCursor() {

        if (
            reduceMotion ||
            window.matchMedia(
                '(pointer: coarse)'
            ).matches
        ) {
            return;
        }


        let cursor =
            $('.rei-cursor');


        if (!cursor) {

            cursor =
                document.createElement(
                    'div'
                );

            cursor.className =
                'rei-cursor-glow';

            document.body.appendChild(
                cursor
            );
        }


        gsap.set(
            cursor,
            {
                xPercent: -50,
                yPercent: -50
            }
        );


        let visible = false;


        window.addEventListener(
            'mousemove',
            event => {

                if (!visible) {

                    visible = true;

                    gsap.to(
                        cursor,
                        {
                            opacity: 1,
                            duration: .25
                        }
                    );
                }


                gsap.to(
                    cursor,
                    {
                        x: event.clientX,
                        y: event.clientY,
                        duration: .35,
                        ease: 'power3.out',
                        overwrite: true
                    }
                );
            }
        );


        document.addEventListener(
            'mouseleave',
            () => {

                visible = false;

                gsap.to(
                    cursor,
                    {
                        opacity: 0,
                        duration: .25
                    }
                );
            }
        );


        $$(
            'a, button, .feature-panel, .city-option, .comp-card'
        ).forEach(element => {

            element.addEventListener(
                'mouseenter',
                () => {

                    gsap.to(
                        cursor,
                        {
                            scale: 1.45,
                            duration: .3,
                            ease: 'power3.out'
                        }
                    );

                }
            );


            element.addEventListener(
                'mouseleave',
                () => {

                    gsap.to(
                        cursor,
                        {
                            scale: 1,
                            duration: .3,
                            ease: 'power3.out'
                        }
                    );

                }
            );

        });
    }


    /* =========================================================
       SCROLL PROGRESS
    ========================================================= */

    function setupScrollProgress() {

        if (
            reduceMotion ||
            !window.ScrollTrigger
        ) {
            return;
        }


        let progress =
            $('.rei-scroll-progress');


        if (!progress) {

            progress =
                document.createElement(
                    'div'
                );

            progress.className =
                'rei-scroll-progress';

            progress.innerHTML =
                '<span></span>';

            document.body.appendChild(
                progress
            );
        }


        const bar =
            $('span', progress);


        gsap.to(
            bar,
            {
                height: '100%',
                ease: 'none',

                scrollTrigger: {
                    start: 0,
                    end: 'max',
                    scrub: true
                }
            }
        );
    }


    /* =========================================================
       HEADER MOTION
    ========================================================= */

    function setupHeaderMotion() {

        const header =
            $('.site-header');


        if (!header) {
            return;
        }


        if (
            reduceMotion ||
            !window.ScrollTrigger
        ) {
            return;
        }


        let previousY = 0;


        ScrollTrigger.create({

            start: 0,

            end: 'max',

            onUpdate: self => {

                const currentY =
                    self.scroll();


                header.classList.toggle(
                    'is-scrolled',
                    currentY > 12
                );


                if (
                    currentY > previousY &&
                    currentY > 160
                ) {

                    gsap.to(
                        header,
                        {
                            yPercent: -110,
                            duration: .35,
                            ease:
                                'power3.out',
                            overwrite: true
                        }
                    );

                } else {

                    gsap.to(
                        header,
                        {
                            yPercent: 0,
                            duration: .45,
                            ease:
                                'power3.out',
                            overwrite: true
                        }
                    );
                }


                previousY =
                    currentY;
            }
        });
    }


    /* =========================================================
       MOBILE MENU MOTION
    ========================================================= */

    function setupMobileMenuMotion() {

        if (
            reduceMotion ||
            !window.gsap
        ) {
            return;
        }


        if (
            !mobileMenu ||
            !menuToggle
        ) {
            return;
        }


        const links =
            $$('#mobile-menu > *');


        const observer =
            new MutationObserver(
                () => {

                    if (
                        !mobileMenu.hidden
                    ) {

                        gsap.fromTo(
                            mobileMenu,
                            {
                                opacity: 0,
                                y: -12
                            },
                            {
                                opacity: 1,
                                y: 0,
                                duration: .35,
                                ease:
                                    'power3.out'
                            }
                        );


                        gsap.fromTo(
                            links,
                            {
                                opacity: 0,
                                y: 18
                            },
                            {
                                opacity: 1,
                                y: 0,
                                duration: .4,
                                stagger: .05,
                                ease:
                                    'power3.out'
                            }
                        );
                    }
                }
            );


        observer.observe(
            mobileMenu,
            {
                attributes: true,
                attributeFilter: [
                    'hidden'
                ]
            }
        );
    }


    /* =========================================================
       HERO MOTION
    ========================================================= */

    function setupHero() {

        if (
            reduceMotion ||
            !window.gsap
        ) {
            return;
        }

        const heroCopy =
            $('.hero-copy');

        if (!heroCopy) {
            return;
        }

        const timeline =
            gsap.timeline({
                defaults: {
                    ease: 'power4.out'
                }
            });

        timeline
            .from(
                $('.eyebrow', heroCopy),
                {
                    y: 25,
                    opacity: 0,
                    duration: .7
                }
            )
            .from(
                $('h1', heroCopy),
                {
                    y: 55,
                    opacity: 0,
                    duration: 1.05
                },
                '-=.3'
            )
            .from(
                $('.hero-lede', heroCopy),
                {
                    y: 25,
                    opacity: 0,
                    duration: .75
                },
                '-=.6'
            )
            .from(
                $('.hero-actions', heroCopy),
                {
                    y: 25,
                    opacity: 0,
                    duration: .75
                },
                '-=.5'
            );
    }


    /* =========================================================
       SCROLL REVEALS
    ========================================================= */

    function setupRevealSections() {

        const platformBarCards = $$('.feature-ml-card, .feature-explain-card');

        if (reduceMotion || !('IntersectionObserver' in window)) {
            platformBarCards.forEach(card => card.classList.add('platform-bars-visible'));
        } else {
            const platformBarObserver = new IntersectionObserver(entries => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('platform-bars-visible');
                        platformBarObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: .3 });

            platformBarCards.forEach(card => platformBarObserver.observe(card));
        }

        if (
            !window.gsap ||
            !window.ScrollTrigger
        ) {
            return;
        }


        const selectors = [
            '.section-intro',
            '.feature-panel',
            '.markets-heading',
            '.city-list',
            '.market-feature',
            '.comparable-copy',
            '.comparable-visual',
            '.valuation-copy',
            '.valuation-visual',
            '.explainability',
            '.final-cta .cta-content',
            '.site-footer'
        ];


        selectors.forEach(
            selector => {

                $$(selector)
                    .forEach(
                        (element, index) => {

                            if (reduceMotion) {

                                gsap.set(
                                    element,
                                    {
                                        opacity: 1,
                                        y: 0
                                    }
                                );

                                return;
                            }


                            gsap.fromTo(
                                element,
                                {
                                    opacity: 0,
                                    y: 55
                                },
                                {
                                    opacity: 1,
                                    y: 0,
                                    duration: .9,
                                    delay:
                                        (index % 3) *
                                        .04,
                                    ease:
                                        'power3.out',

                                    scrollTrigger: {
                                        trigger:
                                            element,

                                        start:
                                            'top 86%',

                                        toggleActions:
                                            'play none none reset',

                                        once: false
                                    }
                                }
                            );
                        }
                    );
            }
        );


        $$('.feature-panel').forEach(card => {
            const copy = $('.feature-panel-copy', card);
            const textLines = copy
                ? $$('.feature-no, h3, p, .panel-link', copy)
                : [];

            if (!textLines.length) {
                return;
            }

            if (reduceMotion) {
                gsap.set(textLines, { opacity: 1, y: 0 });
                return;
            }

            gsap.fromTo(
                textLines,
                { opacity: 0, y: 18 },
                {
                    opacity: 1,
                    y: 0,
                    duration: .65,
                    stagger: .1,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger: card,
                        start: 'top 84%',
                        toggleActions: 'play none none reset'
                    }
                }
            );
        });

        const valuationRevealGroups = [
            {
                trigger: $('.valuation-copy'),
                elements: $$('.eyebrow, h2, p', $('.valuation-copy') || document)
            },
            {
                trigger: $('.valuation-visual'),
                elements: $$('.valuation-label-row, .valuation-numbers > div, .comparison-meter, .valuation-sources', $('.valuation-visual') || document)
            },
            {
                trigger: $('.explain-copy'),
                elements: $$('.feature-no, h3, p', $('.explain-copy') || document)
            },
            {
                trigger: $('.factor-explorer'),
                elements: $$('.factor-group, .factor-detail', $('.factor-explorer') || document)
            }
        ];

        valuationRevealGroups.forEach(({ trigger, elements }) => {
            if (!trigger || !elements.length) {
                return;
            }

            if (reduceMotion) {
                gsap.set(elements, { opacity: 1, y: 0 });
                return;
            }

            gsap.fromTo(
                elements,
                { opacity: 0, y: 18 },
                {
                    opacity: 1,
                    y: 0,
                    duration: .65,
                    stagger: .09,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger,
                        start: 'top 82%',
                        toggleActions: 'play none none reset'
                    }
                }
            );
        });
    }


    /* =========================================================
       FEATURE CARD 3D TILT
    ========================================================= */

    function setupFeatureTilt() {

        if (
            reduceMotion ||
            !window.gsap
        ) {
            return;
        }


        $$('.feature-panel')
            .forEach(card => {

                card.addEventListener(
                    'mousemove',
                    event => {

                        const rect =
                            card.getBoundingClientRect();


                        const px =
                            (
                                event.clientX -
                                rect.left
                            ) /
                            rect.width;


                        const py =
                            (
                                event.clientY -
                                rect.top
                            ) /
                            rect.height;


                        const rotationX =
                            (.5 - py) * 3.5;


                        const rotationY =
                            (px - .5) * 4.5;


                        gsap.to(
                            card,
                            {
                                rotationX,
                                rotationY,
                                y: -5,
                                transformPerspective:
                                    1100,
                                duration: .4,
                                ease:
                                    'power3.out',
                                overwrite: true
                            }
                        );
                    }
                );


                card.addEventListener(
                    'mouseleave',
                    () => {

                        gsap.to(
                            card,
                            {
                                rotationX: 0,
                                rotationY: 0,
                                y: 0,
                                duration: .65,
                                ease:
                                    'power3.out',
                                overwrite: true
                            }
                        );
                    }
                );
            });
    }


    /* =========================================================
       MAGNETIC BUTTONS
    ========================================================= */

    function setupMagneticButtons() {

        if (
            reduceMotion ||
            !window.gsap
        ) {
            return;
        }


        $$('.button, .header-cta, .market-arrow')
            .forEach(element => {

                element.addEventListener(
                    'mousemove',
                    event => {

                        const rect =
                            element.getBoundingClientRect();


                        const x =
                            event.clientX -
                            rect.left -
                            rect.width / 2;


                        const y =
                            event.clientY -
                            rect.top -
                            rect.height / 2;


                        gsap.to(
                            element,
                            {
                                x: x * .10,
                                y: y * .10,
                                duration: .35,
                                ease:
                                    'power3.out',
                                overwrite: true
                            }
                        );
                    }
                );


                element.addEventListener(
                    'mouseleave',
                    () => {

                        gsap.to(
                            element,
                            {
                                x: 0,
                                y: 0,
                                duration: .65,
                                ease:
                                    'elastic.out(1,.45)',
                                overwrite: true
                            }
                        );
                    }
                );
            });
    }


    /* =========================================================
       RIPPLE EFFECT
    ========================================================= */

    function setupRipple() {

        $$('.button, .header-cta, .market-arrow')
            .forEach(button => {

                if (
                    button.dataset.rippleReady
                ) {
                    return;
                }


                button.dataset.rippleReady =
                    'true';

                button.style.position =
                    'relative';

                button.style.overflow =
                    'hidden';


                button.addEventListener(
                    'click',
                    event => {

                        const rect =
                            button.getBoundingClientRect();


                        const ripple =
                            document.createElement(
                                'span'
                            );


                        ripple.className =
                            'rei-ripple';


                        ripple.style.left =
                            `${
                                event.clientX -
                                rect.left
                            }px`;


                        ripple.style.top =
                            `${
                                event.clientY -
                                rect.top
                            }px`;


                        button.appendChild(
                            ripple
                        );


                        ripple.addEventListener(
                            'animationend',
                            () => {
                                ripple.remove();
                            }
                        );
                    }
                );
            });
    }


    /* =========================================================
       COMPARABLE PROPERTY ANIMATION
    ========================================================= */

    function setupComparableMotion() {

        if (
            !window.gsap
        ) {
            return;
        }


        const outer =
            $('.orbit-outer');

        const inner =
            $('.orbit-inner');


        if (
            !reduceMotion &&
            outer
        ) {

            gsap.to(
                outer,
                {
                    rotation: 360,
                    duration: 34,
                    ease: 'none',
                    repeat: -1
                }
            );
        }


        if (
            !reduceMotion &&
            inner
        ) {

            gsap.to(
                inner,
                {
                    rotation: -360,
                    duration: 24,
                    ease: 'none',
                    repeat: -1
                }
            );
        }


        $$('.comp-card')
            .forEach(card => {

                card.addEventListener(
                    'mouseenter',
                    () => {

                        if (
                            reduceMotion
                        ) {
                            return;
                        }

                        gsap.to(
                            card,
                            {
                                scale: 1.035,
                                y: -5,
                                duration: .35,
                                ease:
                                    'power3.out',
                                overwrite: true
                            }
                        );
                    }
                );


                card.addEventListener(
                    'mouseleave',
                    () => {

                        if (
                            reduceMotion
                        ) {
                            return;
                        }

                        gsap.to(
                            card,
                            {
                                scale: 1,
                                y: 0,
                                duration: .45,
                                ease:
                                    'power3.out',
                                overwrite: true
                            }
                        );
                    }
                );
            });
    }


    /* =========================================================
       VALUATION MOTION
    ========================================================= */

    function setupValuationMotion() {

        if (
            !window.ScrollTrigger ||
            !window.gsap
        ) {
            return;
        }


        const visual =
            $('.valuation-visual');


        if (!visual) {
            return;
        }


        ScrollTrigger.create({

            trigger: visual,

            start: 'top 80%',

            once: false,

            onEnter: () => {

                visual.classList.add(
                    'rei-meter-ready'
                );


                if (!reduceMotion) {

                    gsap.fromTo(
                        '.meter-estimate',
                        {
                            width: '0%'
                        },
                        {
                            width: '72%',
                            duration: 1.3,
                            ease:
                                'power3.out'
                        }
                    );


                    gsap.fromTo(
                        '.meter-asking',
                        {
                            width: '0%'
                        },
                        {
                            width: '88%',
                            duration: 1.5,
                            delay: .1,
                            ease:
                                'power3.out'
                        }
                    );


                    gsap.fromTo(
                        '.premium-callout',
                        {
                            opacity: 0,
                            y: 15
                        },
                        {
                            opacity: 1,
                            y: 0,
                            duration: .7,
                            delay: .6,
                            ease:
                                'power3.out'
                        }
                    );
                }
            }
        });


        const explanation =
            $('.factor-explorer');


        if (explanation) {

            ScrollTrigger.create({

                trigger: explanation,

                start: 'top 85%',

                once: false,

                onEnter: () => {

                    explanation.classList.add(
                        'rei-factor-ready'
                    );


                    if (!reduceMotion) {

                        gsap.fromTo(
                            '.factor-button i b',
                            {
                                width: '0%'
                            },
                            {
                                width:
                                    function () {
                                        return getComputedStyle(
                                            this.parentNode
                                        ).getPropertyValue(
                                            '--bar'
                                        );
                                    },
                                duration: 1,
                                stagger: .08,
                                ease:
                                    'power3.out'
                            }
                        );
                    }
                }
            });
        }
    }


    /* =========================================================
       FACTOR MOTION
    ========================================================= */

    function setupFactorMotion() {

        $$('.factor-button')
            .forEach(button => {

                button.addEventListener(
                    'click',
                    () => {

                        if (
                            !window.gsap ||
                            reduceMotion
                        ) {
                            return;
                        }


                        gsap.fromTo(
                            '#factor-detail',
                            {
                                opacity: .35,
                                y: 8
                            },
                            {
                                opacity: 1,
                                y: 0,
                                duration: .4,
                                ease:
                                    'power3.out'
                            }
                        );


                        gsap.fromTo(
                            button,
                            {
                                scale: .98
                            },
                            {
                                scale: 1,
                                duration: .45,
                                ease:
                                    'elastic.out(1,.4)'
                            }
                        );
                    }
                );
            });
    }


    /* =========================================================
       MARKET IMAGE MOTION
    ========================================================= */

    function setupMarketMotion() {

        const architecture =
            $('.market-architecture');


        if (
            !architecture ||
            !window.gsap
        ) {
            return;
        }


        if (!reduceMotion) {

            gsap.to(
                architecture,
                {
                    y: -10,
                    scale: 1.015,
                    duration: 5,
                    ease: 'sine.inOut',
                    repeat: -1,
                    yoyo: true
                }
            );


            $$('.market-tree')
                .forEach(
                    (tree, index) => {

                        gsap.to(
                            tree,
                            {
                                y:
                                    index % 2
                                        ? -7
                                        : -4,

                                duration:
                                    3 +
                                    index,

                                ease:
                                    'sine.inOut',

                                repeat: -1,
                                yoyo: true
                            }
                        );
                    }
                );
        }
    }


    /* =========================================================
       HERO VISUAL MICRO MOTION
    ========================================================= */

    function setupHeroMicroMotion() {

        if (
            reduceMotion ||
            !window.gsap
        ) {
            return;
        }


        $$('.hero-data-card, .architecture-caption')
            .forEach(
                (element, index) => {

                    gsap.to(
                        element,
                        {
                            y:
                                index % 2
                                    ? -5
                                    : -8,

                            duration:
                                3.5 +
                                index * .3,

                            ease:
                                'sine.inOut',

                            repeat: -1,
                            yoyo: true
                        }
                    );
                }
            );
    }


    /* =========================================================
       CTA PARALLAX
    ========================================================= */

    function setupCTAParallax() {

        if (
            reduceMotion ||
            !window.gsap ||
            !window.ScrollTrigger
        ) {
            return;
        }


        const cta =
            $('.final-cta');

        const architecture =
            $('.cta-architecture');


        if (
            !cta ||
            !architecture
        ) {
            return;
        }


        gsap.fromTo(
            architecture,
            {
                yPercent: -5,
                scale: 1.04
            },
            {
                yPercent: 5,
                scale: 1.08,
                ease: 'none',

                scrollTrigger: {
                    trigger: cta,
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: 1
                }
            }
        );


        $$('.cta-tower')
            .forEach(
                (tower, index) => {

                    gsap.to(
                        tower,
                        {
                            y:
                                index % 2 === 0
                                    ? -15
                                    : -9,

                            scrollTrigger: {
                                trigger: cta,
                                start: 'top bottom',
                                end: 'bottom top',
                                scrub: 1
                            }
                        }
                    );
                }
            );
    }


    /* =========================================================
       FOOTER MOTION
    ========================================================= */

    function setupFooterMotion() {

        if (
            reduceMotion ||
            !window.gsap ||
            !window.ScrollTrigger
        ) {
            return;
        }


        const footer =
            $('.site-footer');


        if (!footer) {
            return;
        }


        gsap.fromTo(
            footer,
            {
                y: 35,
                opacity: 0
            },
            {
                y: 0,
                opacity: 1,
                duration: .9,
                ease:
                    'power3.out',

                scrollTrigger: {
                    trigger: footer,
                    start: 'top 92%',
                    once: false
                }
            }
        );
    }


    /* =========================================================
       AUTH MODAL MOTION
    ========================================================= */

    function setupAuthMotion() {

        if (!modal) {
            return;
        }


        const observer =
            new MutationObserver(
                () => {

                    if (
                        !modal.hidden &&
                        !reduceMotion &&
                        window.gsap
                    ) {

                        gsap.fromTo(
                            '.auth-modal',
                            {
                                opacity: 0,
                                y: 30,
                                scale: .96
                            },
                            {
                                opacity: 1,
                                y: 0,
                                scale: 1,
                                duration: .45,
                                ease:
                                    'power3.out'
                            }
                        );
                    }
                }
            );


        observer.observe(
            modal,
            {
                attributes: true,
                attributeFilter: [
                    'hidden'
                ]
            }
        );
    }


    /* =========================================================
       SECTION PARALLAX
    ========================================================= */

    function setupSectionParallax() {

        if (
            reduceMotion ||
            !window.gsap ||
            !window.ScrollTrigger
        ) {
            return;
        }


        const heroImage =
            $('.architecture-image');

        const comparable =
            $('.comparable-visual');

        const valuation =
            $('.valuation-visual');


        if (heroImage) {

            gsap.to(
                heroImage,
                {
                    y: 35,
                    ease: 'none',

                    scrollTrigger: {
                        trigger: '.hero',
                        start: 'top top',
                        end: 'bottom top',
                        scrub: 1
                    }
                }
            );
        }


        if (comparable) {

            gsap.fromTo(
                comparable,
                {
                    y: 35
                },
                {
                    y: -35,
                    ease: 'none',

                    scrollTrigger: {
                        trigger:
                            '.comparables',
                        start:
                            'top bottom',
                        end:
                            'bottom top',
                        scrub: 1
                    }
                }
            );
        }


        if (valuation) {

            gsap.fromTo(
                valuation,
                {
                    y: 25
                },
                {
                    y: -25,
                    ease: 'none',

                    scrollTrigger: {
                        trigger:
                            '.valuation',
                        start:
                            'top bottom',
                        end:
                            'bottom top',
                        scrub: 1
                    }
                }
            );
        }
    }


    /* =========================================================
       DARK / LIGHT TRANSITION EFFECT
    ========================================================= */

    function setupSectionTransitions() {

        if (
            reduceMotion ||
            !window.gsap ||
            !window.ScrollTrigger
        ) {
            return;
        }


        $$('.section-space')
            .forEach(section => {

                gsap.fromTo(
                    section,
                    {
                        clipPath:
                            'inset(0 0 3% 0)'
                    },
                    {
                        clipPath:
                            'inset(0 0 0% 0)',

                        scrollTrigger: {
                            trigger: section,
                            start: 'top 92%',
                            end: 'top 55%',
                            scrub: 1
                        }
                    }
                );
            });
    }


    /* =========================================================
       SCROLL-BASED ARCHITECTURE ELEMENTS
    ========================================================= */

    function setupArchitectureElements() {

        if (
            reduceMotion ||
            !window.gsap ||
            !window.ScrollTrigger
        ) {
            return;
        }


        $$('.tower')
            .forEach(
                (tower, index) => {

                    gsap.fromTo(
                        tower,
                        {
                            y:
                                index % 2 === 0
                                    ? 20
                                    : 35,

                            opacity: .75
                        },
                        {
                            y: 0,
                            opacity: 1,

                            scrollTrigger: {
                                trigger:
                                    '.hero',
                                start:
                                    'top bottom',
                                end:
                                    'center center',
                                scrub: 1
                            }
                        }
                    );
                }
            );


        $$('.cta-tower')
            .forEach(
                (tower, index) => {

                    gsap.fromTo(
                        tower,
                        {
                            y: 35,
                            opacity: .6
                        },
                        {
                            y: 0,
                            opacity: 1,

                            scrollTrigger: {
                                trigger:
                                    '.final-cta',
                                start:
                                    'top bottom',
                                end:
                                    'center center',
                                scrub: 1
                            }
                        }
                    );
                }
            );
    }


    /* =========================================================
       HOVER IMAGE / VISUAL EFFECTS
    ========================================================= */

    function setupVisualHover() {

        if (
            reduceMotion ||
            !window.gsap
        ) {
            return;
        }


        $(
            '.architecture-image, .market-architecture, .comparable-visual, .valuation-visual'
        );


        $$('.architecture-image, .market-architecture')
            .forEach(visual => {

                visual.addEventListener(
                    'mousemove',
                    event => {

                        const rect =
                            visual.getBoundingClientRect();


                        const x =
                            (
                                event.clientX -
                                rect.left
                            ) /
                            rect.width -
                            .5;


                        const y =
                            (
                                event.clientY -
                                rect.top
                            ) /
                            rect.height -
                            .5;


                        gsap.to(
                            visual,
                            {
                                rotationY:
                                    x * 3,
                                rotationX:
                                    -y * 3,
                                transformPerspective:
                                    1000,
                                duration: .5,
                                ease:
                                    'power3.out',
                                overwrite: true
                            }
                        );
                    }
                );


                visual.addEventListener(
                    'mouseleave',
                    () => {

                        gsap.to(
                            visual,
                            {
                                rotationX: 0,
                                rotationY: 0,
                                duration: .7,
                                ease:
                                    'power3.out'
                            }
                        );
                    }
                );
            });
    }


    /* =========================================================
       REFRESH
    ========================================================= */

    function refreshScrollTrigger() {

        if (
            window.ScrollTrigger
        ) {

            window.setTimeout(
                () => {

                    ScrollTrigger.refresh();

                },
                250
            );
        }
    }


    /* =========================================================
       INITIALIZE MOTION SYSTEM
    ========================================================= */

    function initializeMotion() {

        if (!initLibraries()) {
            return;
        }


        body.classList.add(
            'motion-ready'
        );


        setupAnchorScrolling();

        setupCursor();

        setupScrollProgress();

        setupHeaderMotion();

        setupMobileMenuMotion();

        setupHero();

        setupRevealSections();

        setupFeatureTilt();

        setupMagneticButtons();

        setupRipple();

        setupComparableMotion();

        setupValuationMotion();

        setupFactorMotion();

        setupMarketMotion();

        setupHeroMicroMotion();

        setupCTAParallax();

        setupFooterMotion();

        setupAuthMotion();

        setupSectionParallax();

        setupSectionTransitions();

        setupArchitectureElements();

        setupVisualHover();


        refreshScrollTrigger();
    }


    /* =========================================================
       MAIN INITIALIZATION
    ========================================================= */

    function initialize() {

        const preferredTheme =
            safeStorageGet(
                'rei-theme'
            );


        setTheme(
            preferredTheme === 'dark'
                ? 'dark'
                : 'light'
        );


        initializeInteractions();

        initializeCitySelector();

        initializeFactors();

        checkAuthentication();

        initializeMotion();
    }


    if (
        document.readyState ===
        'loading'
    ) {

        document.addEventListener(
            'DOMContentLoaded',
            initialize,
            {
                once: false
            }
        );

    } else {

        initialize();
    }


    /* =========================================================
       RESIZE
    ========================================================= */

    let resizeTimer = null;


    window.addEventListener(
        'resize',
        () => {

            clearTimeout(
                resizeTimer
            );


            resizeTimer =
                window.setTimeout(
                    () => {

                        refreshScrollTrigger();

                    },
                    250
                );

        },
        {
            passive: true
        }
    );

    /* =========================================================
       BACK TO TOP
    ========================================================= */

    const backToTopButton = $('#back-to-top');

    if (backToTopButton) {
        let backToTopVisible = false;
        let backToTopHideTimer = null;

        const syncBackToTop = () => {
            const shouldShow = window.scrollY > 480;

            if (shouldShow === backToTopVisible) {
                return;
            }

            backToTopVisible = shouldShow;
            window.clearTimeout(backToTopHideTimer);

            if (shouldShow) {
                backToTopButton.hidden = false;
                window.requestAnimationFrame(() => {
                    backToTopButton.classList.add('is-visible');
                });
                return;
            }

            backToTopButton.classList.remove('is-visible');
            backToTopHideTimer = window.setTimeout(() => {
                backToTopButton.hidden = true;
            }, 260);
        };

        window.addEventListener('scroll', syncBackToTop, { passive: true });
        backToTopButton.addEventListener('click', () => {
            if (lenis) {
                lenis.scrollTo(0, { duration: 1.1 });
            } else {
                window.scrollTo({
                    top: 0,
                    behavior: reduceMotion ? 'auto' : 'smooth'
                });
            }
        });

        syncBackToTop();
    }

})();