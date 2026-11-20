// Google Analytics 4. Loads gtag on the production host only.
(() => {
    const ID = 'G-G0PNG1LWG5';
    if (location.hostname !== 'psy-fi.space') return;
    const s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag() {
        dataLayer.push(arguments);
    }
    gtag('js', new Date());
    gtag('config', ID);
})();
