from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


# ==========================
# Custom User Model
# ==========================
class CustomerUser(models.Model):

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('banned', 'Banned'),
    )

    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    full_name = models.CharField(max_length=150, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        blank=True,
        null=True
    )

    dob = models.DateField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    # Daily Preferences (Smart Planner)
    work_start_time = models.TimeField(default="09:00")
    work_end_time = models.TimeField(default="17:00")
    preferred_focus_duration = models.IntegerField(default=60)
    preferred_reminder_minutes_before = models.IntegerField(default=15)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    last_login = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


# ==========================
# Category Model
# ==========================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# ==========================
# Task Model
# ==========================
class Task(models.Model):

    PRIORITY_CHOICES = (
        (1, 'High'),
        (2, 'Medium'),
        (3, 'Low'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    )

    RECURRENCE_CHOICES = (
        ('none', 'None'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )

    task_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomerUser, on_delete=models.CASCADE, related_name='tasks')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)

    due_date = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    completed_at = models.DateTimeField(blank=True, null=True)

    # Recurring Detection
    recurrence_pattern = models.CharField(
        max_length=20,
        choices=RECURRENCE_CHOICES,
        default='none'
    )

    bookmarked = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'due_date']
        indexes = [
            models.Index(fields=['user', 'priority']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def save(self, *args, **kwargs):
        if self.due_date and self.due_date < timezone.now() and self.status == 'pending':
            self.status = 'overdue'
        super().save(*args, **kwargs)


# ==========================
# Reminder Model
# ==========================
class Reminder(models.Model):


    reminder_id = models.AutoField(primary_key=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reminders')

    reminder_time = models.DateTimeField()
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Reminder for {self.task.title}"



# ==========================
# ML Model Monitoring
# ==========================
class MLModelLog(models.Model):

    MODEL_TYPES = (
        ('task_ordering', 'Task Ordering'),
        ('recurring_detection', 'Recurring Detection'),
        ('time_prediction', 'Time Prediction'),
    )

    model_type = models.CharField(max_length=50, choices=MODEL_TYPES)
    version = models.CharField(max_length=50)
    accuracy = models.FloatField(blank=True, null=True)

    trained_on = models.DateTimeField(auto_now_add=True)
    last_retrained = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.model_type} v{self.version}"


# ==========================
# Activity Log
# ==========================
class ActivityLog(models.Model):
    """
    Tracks important user actions in the system for auditing and user activity history.
    """
    ACTION_TYPES = (
        ('register',        'Register'),
        ('login',           'Login'),
        ('logout',          'Logout'),
        ('profile_update',  'Profile Update'),
        ('task_create',     'Create Task'),
        ('task_update',     'Update Task'),
        ('task_delete',     'Delete Task'),
        ('task_complete',   'Complete Task'),
        ('reminder_create', 'Create Reminder'),
        ('reminder_update', 'Update Reminder'),
        ('reminder_delete', 'Delete Reminder'),
    )

    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'CustomerUser',
        on_delete=models.CASCADE,
        related_name='activities'
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_TYPES,
        help_text="Type of action performed by the user"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Human-readable details about what happened"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this action occurred"
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"

    def __str__(self):
        return f"{self.user.username} • {self.get_action_display()} • {self.timestamp:%Y-%m-%d %H:%M}"


# ==========================
# Signal: Auto Log Task Creation
# ==========================
@receiver(post_save, sender=Task)
def log_task_creation(sender, instance, created, **kwargs):
    if created:
        ActivityLog.objects.create(
            user=instance.user,
            action='create_task',
            description=f'Task "{instance.title}" created.'
        )