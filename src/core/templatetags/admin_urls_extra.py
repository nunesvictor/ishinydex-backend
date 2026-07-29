from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def preserve_get_params(context, **kwargs):
    request = context.get("request")

    if not request:
        return ""

    get_params = request.GET.copy()

    for key, value in kwargs.items():
        if value is not None and value != "":
            get_params[key] = str(value)
        elif key in get_params:
            del get_params[key]

    return get_params.urlencode()
