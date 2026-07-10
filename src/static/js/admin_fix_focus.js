(function ($) {
    ("use strict");

    function forceInputFocus() {
        const $btn = $('input[name="_moveon"]');

        if ($btn.length) {
            $btn.focus();
        }
    }

    $(document).ready(function () {
        $("#add_id_specimen").focus();

        $(document).on(
            "click",
            ".related-lookup, .add-related, .change-related, .delete-related",
            function (e) {
                setTimeout(function () {
                    if (window.active_popup && !window.active_popup.closed) {
                        linkWindowCloseEvent(window.active_popup);
                    }
                }, 200);
            },
        );

        const originalOpen = window.open;
        window.open = function (...args) {
            const popup = originalOpen.apply(this, args);
            if (popup) {
                linkWindowCloseEvent(popup);
            }
            return popup;
        };

        function linkWindowCloseEvent(popupWindow) {
            popupWindow.addEventListener("unload", function () {
                setTimeout(forceInputFocus, 50);
            });
        }
    });
})(django.jQuery);
