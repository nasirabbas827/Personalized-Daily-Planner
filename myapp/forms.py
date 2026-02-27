from django import forms
from django.contrib.auth.hashers import make_password
from .models import CustomerUser, Task


# ────────────────────────────────────────────────
#               REGISTER FORM
# ────────────────────────────────────────────────
class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'}),
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
        label="Confirm Password"
    )

    class Meta:
        model = CustomerUser
        fields = ['username', 'email', 'full_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.password = make_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


# ────────────────────────────────────────────────
#                 LOGIN FORM
# ────────────────────────────────────────────────
class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )


# ────────────────────────────────────────────────
#               EDIT PROFILE FORM
# ────────────────────────────────────────────────

class EditProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerUser
        fields = [
            'full_name',
            'email',
            'profile_image',
            'bio',
            'phone',
            'gender',
            'dob',
            'country',
            'work_start_time',
            'work_end_time',
            'preferred_focus_duration',
            'preferred_reminder_minutes_before',
        ]

        widgets = {
            # Personal Info
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),

            # Planner Preferences
            'work_start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'work_end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'preferred_focus_duration': forms.NumberInput(attrs={'class': 'form-control', 'min': 15}),
            'preferred_reminder_minutes_before': forms.NumberInput(attrs={'class': 'form-control', 'min': 5}),
        }


# ────────────────────────────────────────────────
#                 TASK FORM  
# ────────────────────────────────────────────────

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title',
            'description',
            'category',
            'priority',
            'due_date',
            'duration_minutes',
            'recurrence_pattern',
            'bookmarked',
            'status',
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter task title...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the task details...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 5
            }),
            'recurrence_pattern': forms.Select(attrs={
                'class': 'form-control'
            }),
            'bookmarked': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }


from django import forms
from .models import Reminder, Task

class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ['task', 'reminder_time', 'is_completed']

        widgets = {
            'task': forms.Select(attrs={'class': 'form-control'}),
            'reminder_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_completed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


