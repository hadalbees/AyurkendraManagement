from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from rolemgmt.models import Role


class CustomUser(AbstractUser):
    staff_id = models.CharField(max_length=15, unique=True, blank=True, null=True)
    menu_permission = models.TextField(blank=True, null=True)  # ✅ Updated
    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_members'
    )
    groups = models.ManyToManyField(Group, related_name='customuser_set', blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name='customuser_set', blank=True)

    def save(self, *args, **kwargs):
        # ✅ Generate sequential staff_id (STF0001, STF0002, etc.)
        if not self.staff_id:
            last_user = CustomUser.objects.order_by('-id').first()
            if last_user and last_user.staff_id and last_user.staff_id.startswith("STF"):
                try:
                    last_number = int(last_user.staff_id.replace("STF", ""))
                except ValueError:
                    last_number = 0
            else:
                last_number = 0

            new_number = last_number + 1
            self.staff_id = f"STF{new_number:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.staff_id})"
