from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Attempt, AttemptAnswer, Option, Question, Quiz, Topic


class OptionInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        correct = sum(
            1 for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
            and form.cleaned_data.get("is_correct")
        )
        if correct != 1:
            raise ValidationError("Each question needs exactly one correct option.")


class OptionInline(admin.TabularInline):
    model = Option
    formset = OptionInlineFormSet
    extra = 2
    min_num = 2
    validate_min = True


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [OptionInline]
    list_display = ["__str__", "quiz", "order"]
    list_filter = ["quiz__topic", "quiz"]
    search_fields = ["text"]


class QuestionInline(admin.TabularInline):
    model = Question
    fields = ["text", "order"]
    extra = 1
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ["title"]}
    inlines = [QuestionInline]
    list_display = ["title", "topic", "pub_date"]
    list_filter = ["topic", "pub_date"]
    search_fields = ["title"]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ["name"]}
    list_display = ["name", "slug"]


class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    can_delete = False
    readonly_fields = ["question", "selected_option", "is_correct"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "quiz", "score", "total", "created"]
    list_filter = ["quiz"]
    readonly_fields = ["user", "quiz", "score", "total", "created"]
    inlines = [AttemptAnswerInline]

    def has_add_permission(self, request):
        return False
