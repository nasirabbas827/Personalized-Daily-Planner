from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
        # Tasks
    path('task/create/', views.create_task, name='create_task'),
    path('task/view/', views.task_list, name='task_list'),
    path('task/edit/<int:task_id>/', views.edit_task, name='edit_task'),
    path('task/delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('task/complete/<int:task_id>/', views.complete_task, name='complete_task'),
    path('reminders/', views.reminder_list, name='reminder_list'),
    path('reminders/new/', views.create_reminder, name='create_reminder'),
    path('reminders/<int:reminder_id>/edit/', views.edit_reminder, name='edit_reminder'),
    path('reminders/<int:reminder_id>/delete/', views.delete_reminder, name='delete_reminder'),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
