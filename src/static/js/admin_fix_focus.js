(function ($) {
    "use strict";

    function forceInputFocus() {
        const moveon_btn = $('input[name="_moveon"]');
        const specimen_repr = $("#id_specimen option:selected").text();
        const banner_img = $(".custom-help-banner-img").first();

        if (specimen_repr.length) {
            let url = banner_img.attr("src");

            if (specimen_repr.indexOf("✨") !== -1) {
                url = url.replace(/\/home\/(?!shiny\/)/, "/home/shiny/");
            } else {
                url = url.replace(/\/home\/shiny\//, "/home/");
            }

            banner_img.css({
                opacity: "0.2",
                transition: "opacity 0.2s ease-in-out",
            });

            banner_img
                .one("load", function () {
                    banner_img.removeClass(
                        "status-unregistred status-blinking",
                    );
                    banner_img.css("opacity", "1");
                })
                .attr("src", url);

            if (banner_img[0].complete) {
                banner_img.trigger("load");
            }
        }

        if (moveon_btn.length) {
            moveon_btn.focus();
        }
    }

    $(document).ready(function () {
        $("#add_id_specimen").focus();

        $(document).on(
            "django:update-related",
            function (e, value, objId, objRepr) {
                setTimeout(function () {
                    forceInputFocus();
                }, 50);
            },
        );
    });
})(django.jQuery);
