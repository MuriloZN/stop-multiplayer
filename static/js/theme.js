(() => {
    const storageKey = "stop-theme";
    const root = document.documentElement;

    function aplicarTema(tema) {
        const temaValido = tema === "light" ? "light" : "dark";
        root.dataset.theme = temaValido;
        try { localStorage.setItem(storageKey, temaValido); } catch (_) {}

        document.querySelectorAll(".theme-toggle").forEach(botao => {
            const claro = temaValido === "light";
            botao.setAttribute("aria-label", claro ? "Ativar tema escuro" : "Ativar tema claro");
            botao.setAttribute("aria-pressed", String(claro));
            botao.innerHTML = claro
                ? '<span class="theme-toggle-icon" aria-hidden="true">☾</span><span>Modo escuro</span>'
                : '<span class="theme-toggle-icon" aria-hidden="true">☀</span><span>Modo claro</span>';
        });
    }

    let temaInicial = "dark";
    try {
        const salvo = localStorage.getItem(storageKey);
        if (salvo === "light" || salvo === "dark") temaInicial = salvo;
    } catch (_) {}

    aplicarTema(temaInicial);

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".theme-toggle").forEach(botao => {
            botao.addEventListener("click", () => {
                aplicarTema(root.dataset.theme === "dark" ? "light" : "dark");
            });
        });
    });
})();