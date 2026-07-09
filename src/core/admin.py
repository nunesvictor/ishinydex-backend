from django.contrib import admin


class TimestampedAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=...):
        fields = super().get_readonly_fields(request, obj)
        return list(set(fields) | set(["created_at", "updated_at"]))
