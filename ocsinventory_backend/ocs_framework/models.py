from django.contrib.auth.models import Group, User
from django.db import models
from django.db.models import Q


class RestrictVisibilityQuerySet(models.QuerySet):
    """
    Queryset shared by the visibility restricted models
    """

    def visible_to(self, user):
        """
        Keep what the user may see: public items, their own, and group items
        shared with one of their groups
        """
        return self.filter(
            Q(visibility="public")
            | Q(user=user)
            | Q(visibility="private_group", groups__in=user.groups.all())
        ).distinct()


class RestrictVisibility(models.Model):
    """
    Abstract class to implement visibility restriction on child models
    """

    class Meta:
        abstract = True

    visibility_choices = [
        ("public", "Public"),
        ("private_personal", "Private (Personal)"),
        ("private_group", "Private (Group)"),
    ]

    visibility = models.CharField(
        max_length=20, choices=visibility_choices, default="private_personal"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    groups = models.ManyToManyField(Group, blank=True)
    allow_group_modification = models.BooleanField(default=False)

    objects = RestrictVisibilityQuerySet.as_manager()
