// Garante que o jQuery do Django fique acessível globalmente para o Select2
if (typeof django !== "undefined" && django.jQuery) {
    window.jQuery = window.$ = django.jQuery;
}
