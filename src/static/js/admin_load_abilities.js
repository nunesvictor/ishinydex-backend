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

            const currentValue = $pokemonAbilitySelect.val();

            $.ajax({
                url: `/api/pokemon/`,
                data: {
                    form_id: formId,
                },
                success: function (data) {
                    let options = '<option value="">---------</option>';
                    data["results"].forEach(function (item) {
                        item.abilities.forEach(function (ability) {
                            const isSelected =
                                ability === currentValue ? "selected" : "";
                            options += `<option value="${ability}" ${isSelected}>${ability}</option>`;
                        });
                    });

                    $pokemonAbilitySelect.html(options).trigger("change");
                },
            });
        });
    }

    $pokemonFormSelect.trigger("change");
});
