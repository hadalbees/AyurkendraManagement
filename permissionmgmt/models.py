from django.db import models
from django.contrib.auth import get_user_model
# MODULE_CHOICES = [
#     ('patient', 'Patient Management'),
#     ('stock', 'Stock Management'),
#     ('attendance', 'Attendance Management'),
#     ('billing', 'Billing & Payments'),
#     ('reports', 'Reports & Dashboard'),
# ]

# class UserPermission(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     module_name = models.CharField(max_length=50, choices=MODULE_CHOICES)
#     can_access = models.BooleanField(default=False)

#     def __str__(self):
#         return f"{self.user.username} - {self.module_name} ({'Access' if self.can_access else 'No Access'})"
