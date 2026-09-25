from accountinfo.services import AccountinfoSearch
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters


class AccountinfoSearchMixin:
    """
    Let the quick search reach the administrative data on display

    Those columns are shown whenever the listing is asked for them, but
    search_fields cannot express them : the values live in a JSON blob on a
    generic relation, not on the listed model.

    A viewset using it declares which data it carries :
        accountinfo_slug = "inventory_base.inventorybase"
        accountinfo_target = "ASSET"
    """

    accountinfo_slug = None
    accountinfo_target = None

    def filter_queryset(self, queryset):
        term = self.request.query_params.get("search")
        accountinfo = self.request.query_params.get("accountinfo")
        asked = accountinfo and accountinfo.lower() == "true"

        if not term or not asked or not self.accountinfo_slug:
            return super().filter_queryset(queryset)

        matched = AccountinfoSearch(
            self.accountinfo_slug, self.accountinfo_target
        ).matching_object_ids(term)

        if not matched:
            return super().filter_queryset(queryset)

        narrowed = DjangoFilterBackend().filter_queryset(self.request, queryset, self)
        on_base_fields = filters.SearchFilter().filter_queryset(
            self.request, narrowed, self
        )

        # narrowed, not queryset : the model filters apply to both sides
        combined = narrowed.filter(
            Q(pk__in=on_base_fields.values("pk")) | Q(pk__in=matched)
        )

        return filters.OrderingFilter().filter_queryset(self.request, combined, self)
