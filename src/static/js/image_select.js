(function ($) {
    "use strict";

    // Injeta estilos adaptativos para tema Claro / Escuro
    var style = document.createElement("style");
    style.innerHTML = `
        /* Suporte ao Tema Escuro (Detecta o navegador e o Django Admin) */
        @media (prefers-color-scheme: dark) {
            .select2-container--default .select2-selection--single {
                background-color: var(--body-bg, #222) !important;
                border-color: var(--border-color, #444) !important;
                color: var(--body-fg, #eee) !important;
            }
            .select2-container--default .select2-selection--single .select2-selection__rendered {
                color: var(--body-fg, #eee) !important;
            }
            .select2-container--default .select2-selection--single .select2-selection__arrow b {
                border-color: var(--body-fg, #eee) transparent transparent transparent !important;
            }
            .select2-dropdown {
                background-color: var(--body-bg, #222) !important;
                border-color: var(--border-color, #444) !important;
                color: var(--body-fg, #eee) !important;
            }
            .select2-search__field {
                background-color: var(--darkened-bg, #333) !important;
                color: var(--body-fg, #eee) !important;
                border-color: var(--border-color, #555) !important;
            }
            .select2-container--default .select2-results__option[aria-selected=true] {
                background-color: var(--darkened-bg, #333) !important;
            }
            .select2-container--default .select2-results__option--highlighted[aria-selected] {
                background-color: var(--primary, #264b5d) !important;
                color: #fff !important;
            }
        }

        /* Compatibilidade com o botão de alternar tema do Django Admin (data-theme="dark") */
        [data-theme="dark"] .select2-container--default .select2-selection--single,
        [data-theme="dark"] .select2-dropdown {
            background-color: var(--body-bg, #222) !important;
            border-color: var(--border-color, #444) !important;
            color: var(--body-fg, #eee) !important;
        }
        [data-theme="dark"] .select2-container--default .select2-selection--single .select2-selection__rendered {
            color: var(--body-fg, #eee) !important;
        }
    `;
    document.head.appendChild(style);

    function formatPokeball(option) {
        if (!option.id || !option.element) {
            return option.text;
        }

        var imageUrl = $(option.element).data("image");
        if (!imageUrl) {
            return option.text;
        }

        return $(
            '<span style="display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;">' +
                '<img src="' +
                imageUrl +
                '" style="width: 20px; height: 20px; object-fit: contain; flex-shrink: 0;" />' +
                "<span>" +
                option.text +
                "</span>" +
                "</span>",
        );
    }

    function getIdealWidth($select) {
        var $test = $("<span>")
            .css({
                position: "absolute",
                visibility: "hidden",
                "white-space": "nowrap",
                "font-size": "13px",
                "font-family": "sans-serif",
            })
            .appendTo("body");

        var maxWidth = 0;
        $select.find("option").each(function () {
            var text = $(this).text();
            if (text) {
                $test.text(text);
                var w = $test.width();
                if (w > maxWidth) {
                    maxWidth = w;
                }
            }
        });

        $test.remove();
        return maxWidth + 68 + "px";
    }

    $(document).ready(function () {
        $("select.select2-image-select").each(function () {
            var $select = $(this);
            var computedWidth = getIdealWidth($select);

            $select.select2({
                templateResult: formatPokeball,
                templateSelection: formatPokeball,
                width: computedWidth,
            });
        });
    });
})(
    window.jQuery ||
        window.$ ||
        (typeof django !== "undefined" ? django.jQuery : jQuery),
);
