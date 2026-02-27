from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os

from .models import (
    CustomerUser, Category, Task,  Reminder,
    MLModelLog, ActivityLog
)

# ==========================
# CustomerUser Admin
# ==========================
@admin.register(CustomerUser)
class CustomerUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'status', 'last_login', 'created_at')
    search_fields = ('username', 'email', 'full_name')
    list_filter = ('status', 'gender', 'country')
    readonly_fields = ('last_login', 'created_at', 'updated_at')


# ==========================
# Category Admin
# ==========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default')
    search_fields = ('name',)
    list_filter = ('is_default',)


# ==========================
# Task Admin with ML Training
# ==========================
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'priority', 'status', 'due_date', 'recurrence_pattern')
    search_fields = ('title', 'description', 'user__username')
    list_filter = ('priority', 'status', 'recurrence_pattern', 'category')
    actions = ['train_logistic_regression']

    def train_logistic_regression(self, request, queryset):
        """
        Admin action: Train Logistic Regression on all tasks
        Predicts task priority from title, description, category, recurrence, and duration
        """

        # Use all tasks, ignoring deleted tasks
        tasks = Task.objects.filter(is_deleted=False)
        if not tasks.exists():
            self.message_user(request, "No tasks available for training!", level=messages.WARNING)
            return

        texts = []
        labels = []

        for task in tasks:
            # Combine title, description, category, recurrence, and duration as feature string
            category_name = task.category.name if task.category else ''
            recurrence = task.recurrence_pattern or ''
            duration = str(task.duration_minutes)
            text = f"{task.title} {task.description or ''} {category_name} {recurrence} {duration}"
            texts.append(text)
            labels.append(task.priority)

        if len(set(labels)) < 2:
            self.message_user(request, "At least two different priorities are required to train.", level=messages.ERROR)
            return

        # TF-IDF vectorization
        vectorizer = TfidfVectorizer(max_features=5000)
        X = vectorizer.fit_transform(texts)
        y = labels

        # Split into train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Logistic Regression with class balancing
        model = LogisticRegression(max_iter=500, class_weight='balanced')
        model.fit(X_train, y_train)

        # Evaluate accuracy
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)

        # Save model & vectorizer
        model_dir = os.path.join(os.getcwd(), 'ml_models')
        os.makedirs(model_dir, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        model_path = os.path.join(model_dir, f"logreg_model_{timestamp}.joblib")
        vectorizer_path = os.path.join(model_dir, f"vectorizer_{timestamp}.joblib")
        joblib.dump(model, model_path)
        joblib.dump(vectorizer, vectorizer_path)

        # Log model in MLModelLog
        MLModelLog.objects.create(
            model_type='task_ordering',
            version=timestamp,
            accuracy=acc,
            last_retrained=timezone.now(),
            notes=f"Trained on {tasks.count()} tasks including category, recurrence, and duration. Model saved at {model_path}."
        )

        self.message_user(
            request,
            f"Logistic Regression trained on {tasks.count()} tasks. Accuracy: {acc:.2f}",
            level=messages.SUCCESS
        )

    train_logistic_regression.short_description = "Train Logistic Regression on all tasks"



# ==========================
# Reminder Admin
# ==========================
@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('task', 'reminder_time',  'is_completed')
    search_fields = ('task__title',)


# ==========================
# MLModelLog Admin
# ==========================
@admin.register(MLModelLog)
class MLModelLogAdmin(admin.ModelAdmin):
    list_display = ('model_type', 'version', 'accuracy', 'trained_on', 'last_retrained')
    search_fields = ('model_type', 'version')
    readonly_fields = ('trained_on', 'last_retrained', 'accuracy')


# ==========================
# ActivityLog Admin
# ==========================
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'timestamp')
    search_fields = ('user__username', 'description')
    list_filter = ('action',)
    readonly_fields = ('timestamp',)