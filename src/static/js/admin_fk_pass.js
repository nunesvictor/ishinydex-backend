window.addEventListener("load", function () {
    const $ = django.jQuery;

    const formField = document.getElementById("id_form");
    const personalDexField = document.getElementById("id_personal_dex");
    const addButton = document.querySelector(".field-specimen .add-related");

    if (formField && addButton) {
        const originalHref = addButton.href;

        function updatePopupUrl() {
            if (formField.value) {
                addButton.href =
                    originalHref +
                    "&form_id=" +
                    formField.value +
                    "&personal_dex_id=" +
                    personalDexField.value;
            } else {
                addButton.href = originalHref;
            }
        }

        formField.addEventListener("change", updatePopupUrl);
        personalDexField.addEventListener("change", updatePopupUrl);
        updatePopupUrl();
    }
});
