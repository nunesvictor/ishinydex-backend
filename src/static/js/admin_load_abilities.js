window.addEventListener("load", function () {
    const $ = django.jQuery;

    const $pokemonFormSelect = $("#id_form");
    const $pokemonAbilitySelect = $("#id_ability");

    if ($pokemonFormSelect.length && $pokemonAbilitySelect.length) {
        $pokemonFormSelect.on("change", function () {
            const formId = $(this).val();

            if (!formId) {
                $pokemonAbilitySelect
                    .html('<option value="">---------</option>')
                    .trigger("change");
                return;
            }

            $.ajax({
                url: `/api/pokemon/`,
                data: {
                    form_id: formId,
                },
                success: function (data) {
                    let options = '<option value="">---------</option>';
                    data["results"].forEach(function (item) {
                        item.abilities.forEach(function (ability) {
                            options += `<option value="${ability}">${ability}</option>`;
                        })
                    });

                    // Update DOM and tell Select2 to redraw if necessary
                    $pokemonAbilitySelect.html(options).trigger("change");
                },
            });
        });
    }

    $pokemonFormSelect.trigger("change");
});
