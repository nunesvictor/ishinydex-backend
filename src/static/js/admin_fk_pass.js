window.addEventListener('load', function() {
    const $ = django.jQuery;

    const parentField = document.getElementById('id_form');
    const addButton = document.querySelector('.field-specimen .add-related');

    if (parentField && addButton) {
        const originalHref = addButton.href;

        function updatePopupUrl() {
            if (parentField.value) {
                addButton.href = originalHref + '&form_id=' + parentField.value;
            } else {
                addButton.href = originalHref;
            }
        }

        parentField.addEventListener('change', updatePopupUrl);
        updatePopupUrl();
    }
});
