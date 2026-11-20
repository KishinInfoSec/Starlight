from django.contrib import admin

from .models import (Challenge, ChallengeFile, Membership, PracticeGroup,
                     SkillObjective, Solve, Submission)


class ChallengeFileInline(admin.TabularInline):
    model = ChallengeFile
    extra = 0


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "difficulty", "points", "pub_date")
    list_filter = ("category", "difficulty")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("skills",)
    inlines = [ChallengeFileInline]


@admin.register(SkillObjective)
class SkillObjectiveAdmin(admin.ModelAdmin):
    list_display = ("framework", "code", "title")
    list_filter = ("framework",)
    search_fields = ("code", "title")


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Solve)
class SolveAdmin(ReadOnlyAdmin):
    list_display = ("user", "challenge", "solved_at")
    list_filter = ("challenge",)


@admin.register(Submission)
class SubmissionAdmin(ReadOnlyAdmin):
    list_display = ("user", "challenge", "correct", "created")
    list_filter = ("correct", "challenge")


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(PracticeGroup)
class PracticeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role", "joined")
    list_filter = ("role",)
