from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.db.models import Count, Q
from django.utils import timezone
import pytz
import os
import joblib
from datetime import timedelta
import plotly.graph_objects as go

from .models import CustomerUser, Task, ActivityLog, Category, Reminder
from .forms import RegisterForm, LoginForm, EditProfileForm, TaskForm, ReminderForm


# ────────────────────────────────────────────────
#                   HELPERS
# ────────────────────────────────────────────────

def get_logged_in_user(request):
    """Retrieve currently logged-in user from session or return None."""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return CustomerUser.objects.filter(user_id=user_id).first()


# ────────────────────────────────────────────────
#               PUBLIC PAGES
# ────────────────────────────────────────────────

def index(request):
    """Landing / home page — no login required."""
    return render(request, 'index.html')


# ────────────────────────────────────────────────
#               AUTHENTICATION
# ────────────────────────────────────────────────

def register_view(request):
    """Handle new user registration."""
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            ActivityLog.objects.create(
                user=user,
                action='register',
                description='New account registered'
            )
            messages.success(request, "Account created successfully. Please log in.")
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


def login_view(request):
    """Custom session-based login (not using Django auth)."""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            try:
                user = CustomerUser.objects.get(username=username)

                if user.status != 'active':
                    messages.error(request, "Your account is not active. Please contact support.")
                    return render(request, 'login.html', {'form': form})

                if check_password(password, user.password):
                    request.session['user_id'] = user.user_id
                    request.session['username'] = user.username

                    ActivityLog.objects.create(
                        user=user,
                        action='login',
                        description='Successful login'
                    )

                    messages.success(request, f"Welcome {user.username}!")
                    return redirect('dashboard')
                else:
                    messages.error(request, "Invalid password.")

            except CustomerUser.DoesNotExist:
                messages.error(request, "User not found.")
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """Clear session and log the user out."""
    user = get_logged_in_user(request)
    if user:
        ActivityLog.objects.create(
            user=user,
            action='logout',
            description='User logged out'
        )

    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect('index')


# ────────────────────────────────────────────────
#               PROFILE MANAGEMENT
# ────────────────────────────────────────────────

def edit_profile(request):
    """Allow user to edit their profile."""
    user = get_logged_in_user(request)
    if not user:
        messages.error(request, "You need to log in first.")
        return redirect('login')

    if request.method == 'POST':
        form = EditProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            ActivityLog.objects.create(
                user=user,
                action='profile_update',
                description='User updated profile settings'
            )
            messages.success(request, "Profile updated successfully.")
            return redirect('dashboard')
    else:
        form = EditProfileForm(instance=user)

    return render(request, 'edit_profile.html', {
        'form': form,
        'user': user,
    })


# ────────────────────────────────────────────────
#               DASHBOARD & ANALYTICS
# ────────────────────────────────────────────────

def get_task_recommendations(user, top_n=5):
    """Load latest ML model → return top-N recommended pending tasks."""
    model_dir = os.path.join(os.getcwd(), 'ml_models')
    model_files = sorted([f for f in os.listdir(model_dir) if f.startswith('logreg_model_')])
    vectorizer_files = sorted([f for f in os.listdir(model_dir) if f.startswith('vectorizer_')])

    if not model_files or not vectorizer_files:
        return []

    model = joblib.load(os.path.join(model_dir, model_files[-1]))
    vectorizer = joblib.load(os.path.join(model_dir, vectorizer_files[-1]))

    tasks = Task.objects.filter(user=user, status='pending', is_deleted=False)
    if not tasks.exists():
        return []

    task_texts = []
    for task in tasks:
        cat = task.category.name if task.category else ''
        rec = task.recurrence_pattern or ''
        dur = str(task.duration_minutes or '')
        text = f"{task.title} {task.description or ''} {cat} {rec} {dur}"
        task_texts.append(text)

    X = vectorizer.transform(task_texts)
    predicted_priority = model.predict(X)

    ranked = sorted(zip(tasks, predicted_priority), key=lambda x: x[1])
    return [task for task, _ in ranked[:top_n]]


def get_recurring_task_suggestions(user, top_n=5):
    """Return up to top_n recurring tasks."""
    return Task.objects.filter(
        user=user,
        is_deleted=False
    ).exclude(
        recurrence_pattern='none'
    )[:top_n]


def dashboard_view(request):
    """Main dashboard with stats, charts, recommendations & reminders."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    tz = pytz.timezone('Asia/Karachi')
    now = timezone.now().astimezone(tz)

    tasks = Task.objects.filter(user=user, is_deleted=False)

    # Auto-update overdue status
    Task.objects.filter(
        user=user,
        status='pending',
        due_date__lt=timezone.now()
    ).update(status='overdue')

    pending   = tasks.filter(status='pending').count()
    completed = tasks.filter(status='completed').count()
    overdue   = tasks.filter(status='overdue').count()
    total     = tasks.count()

    # ── Tasks per Category ───────────────────────────────────────────
    categories = Category.objects.all()
    tasks_per_category = {cat.name: tasks.filter(category=cat).count() for cat in categories}

    category_fig = go.Figure([go.Bar(
        x=list(tasks_per_category.keys()),
        y=list(tasks_per_category.values()),
        marker_color='rgb(54, 162, 235)'
    )])
    category_fig.update_layout(
        title="Tasks per Category",
        xaxis_title="Category",
        yaxis_title="Count",
        template="plotly_white",
        height=400
    )
    category_chart = category_fig.to_html(full_html=False)

    # ── Completion Rates Pie ─────────────────────────────────────────
    completion_fig = go.Figure(data=[go.Pie(
        labels=['Completed', 'Pending', 'Overdue'],
        values=[completed, pending, overdue],
        hole=0.4
    )])
    completion_fig.update_layout(title="Completion Rates", template="plotly_white", height=400)
    completion_chart = completion_fig.to_html(full_html=False)

    # ── Weekly Completion Trend ──────────────────────────────────────
    last_7_days = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
    completed_per_day = [
        tasks.filter(status='completed', completed_at__date=day).count()
        for day in last_7_days
    ]

    weekly_fig = go.Figure([go.Scatter(
        x=[d.strftime("%a %d") for d in last_7_days],
        y=completed_per_day,
        mode='lines+markers',
        line=dict(color='green', width=2)
    )])
    weekly_fig.update_layout(
        title="Tasks Completed – Last 7 Days",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white",
        height=400
    )
    weekly_chart = weekly_fig.to_html(full_html=False)

    # ── Upcoming reminders ───────────────────────────────────────────
    upcoming_reminders = Reminder.objects.filter(
        task__user=user,
        reminder_time__gte=timezone.now(),
        is_completed=False
    ).order_by('reminder_time')[:5]

    for r in upcoming_reminders:
        r.reminder_time = r.reminder_time.astimezone(tz)

    context = {
        'user': user,
        'greeting': "Good Morning" if now.hour < 12 else "Good Afternoon" if now.hour < 17 else "Good Evening",
        'total_tasks': total,
        'pending_tasks': pending,
        'completed_tasks': completed,
        'overdue_tasks': overdue,
        'tasks_per_category': tasks_per_category,
        'upcoming_reminders': upcoming_reminders,
        'recommended_tasks': get_task_recommendations(user),
        'recurring_suggestions': get_recurring_task_suggestions(user),
        'category_chart': category_chart,
        'completion_chart': completion_chart,
        'weekly_chart': weekly_chart,
    }

    return render(request, 'dashboard.html', context)


# ────────────────────────────────────────────────
#                   TASK MANAGEMENT
# ────────────────────────────────────────────────

def create_task(request):
    """Create a new task."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = user
            task.save()

            ActivityLog.objects.create(
                user=user,
                action='create_task',
                description=f'Task created: "{task.title}"'
            )

            messages.success(request, "Task created successfully.")
            return redirect('dashboard')
    else:
        form = TaskForm()

    return render(request, 'task_form.html', {'form': form})


def task_list(request):
    """List tasks with filtering & stats."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    # Auto-mark overdue
    Task.objects.filter(
        user=user,
        status='pending',
        due_date__lt=timezone.now()
    ).update(status='overdue')

    tasks = Task.objects.filter(user=user, is_deleted=False)

    # Filters
    priority_filter = request.GET.get('priority')
    status_filter   = request.GET.get('status')
    category_filter = request.GET.get('category')
    search_query    = request.GET.get('search')
    bookmarked      = request.GET.get('bookmarked')

    if priority_filter and priority_filter.isdigit():
        tasks = tasks.filter(priority=int(priority_filter))

    if status_filter:
        tasks = tasks.filter(status=status_filter)

    if category_filter and category_filter.isdigit():
        tasks = tasks.filter(category_id=int(category_filter))

    if bookmarked == "1":
        tasks = tasks.filter(bookmarked=True)

    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    tasks = tasks.order_by('priority', 'due_date')

    context = {
        'user': user,
        'tasks': tasks,
        'categories': Category.objects.all(),
        'total_tasks': tasks.count(),
        'completed_tasks': tasks.filter(status='completed').count(),
        'pending_tasks': tasks.filter(status='pending').count(),
        'overdue_tasks': tasks.filter(status='overdue').count(),
    }

    return render(request, 'task_list.html', context)


def edit_task(request, task_id):
    """Edit existing task."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    task = get_object_or_404(Task, task_id=task_id, user=user)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            ActivityLog.objects.create(
                user=user,
                action='update_task',
                description=f'Task updated: "{task.title}"'
            )
            messages.success(request, "Task updated successfully.")
            return redirect('dashboard')
    else:
        form = TaskForm(instance=task)

    return render(request, 'task_form.html', {'form': form})


def delete_task(request, task_id):
    """Soft-delete task."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    task = get_object_or_404(Task, task_id=task_id, user=user)
    title = task.title
    task.is_deleted = True
    task.save()

    ActivityLog.objects.create(
        user=user,
        action='delete_task',
        description=f'Task deleted: "{title}"'
    )

    messages.success(request, "Task moved to trash.")
    return redirect('dashboard')


def complete_task(request, task_id):
    """Mark task as completed."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    task = get_object_or_404(Task, task_id=task_id, user=user)
    task.status = 'completed'
    task.completed_at = timezone.now()
    task.save()

    ActivityLog.objects.create(
        user=user,
        action='complete_task',
        description=f'Task completed: "{task.title}"'
    )

    messages.success(request, "Task marked as completed!")
    return redirect('dashboard')


# ────────────────────────────────────────────────
#                 REMINDER MANAGEMENT
# ────────────────────────────────────────────────

def create_reminder(request):
    """Create reminder for user's own task."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    if request.method == 'POST':
        form = ReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            if reminder.task.user != user:
                messages.error(request, "Invalid task selected.")
                return redirect('reminder_list')
            reminder.save()

            ActivityLog.objects.create(
                user=user,
                action='create_task',  # ← change to 'reminder_create' if you add it
                description=f'Reminder created for task "{reminder.task.title}"'
            )

            messages.success(request, "Reminder created successfully.")
            return redirect('reminder_list')
    else:
        form = ReminderForm()
        form.fields['task'].queryset = Task.objects.filter(user=user, is_deleted=False)

    return render(request, 'reminder_form.html', {'form': form})


def edit_reminder(request, reminder_id):
    """Edit existing reminder."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    reminder = get_object_or_404(Reminder, pk=reminder_id)
    if reminder.task.user != user:
        messages.error(request, "You cannot edit this reminder.")
        return redirect('reminder_list')

    if request.method == 'POST':
        form = ReminderForm(request.POST, instance=reminder)
        if form.is_valid():
            form.save()
            ActivityLog.objects.create(
                user=user,
                action='update_task',  # ← change to 'reminder_update' if added
                description=f'Reminder updated for task "{reminder.task.title}"'
            )
            messages.success(request, "Reminder updated successfully.")
            return redirect('reminder_list')
    else:
        form = ReminderForm(instance=reminder)
        form.fields['task'].queryset = Task.objects.filter(user=user, is_deleted=False)

    return render(request, 'reminder_form.html', {'form': form})


def delete_reminder(request, reminder_id):
    """Delete reminder."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    reminder = get_object_or_404(Reminder, pk=reminder_id)
    if reminder.task.user != user:
        messages.error(request, "You cannot delete this reminder.")
        return redirect('reminder_list')

    task_title = reminder.task.title
    reminder.delete()

    ActivityLog.objects.create(
        user=user,
        action='delete_task',  # ← change to 'reminder_delete' if added
        description=f'Reminder deleted for task "{task_title}"'
    )

    messages.success(request, "Reminder deleted successfully.")
    return redirect('reminder_list')


def reminder_list(request):
    """List all reminders for user's tasks."""
    user = get_logged_in_user(request)
    if not user:
        return redirect('login')

    reminders = Reminder.objects.filter(task__user=user).order_by('reminder_time')
    return render(request, 'reminder_list.html', {'reminders': reminders})