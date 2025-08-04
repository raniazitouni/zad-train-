import django_filters
from .models import Curriculum, Chapter, Lesson, Assessment, Enrollment, Note, Feedback, Materials, Evaluation


# Curriculum's filterset
class CurriculumFilter(django_filters.FilterSet):
    class Meta:
        model = Curriculum
        fields = {
            "id": ["exact"],
            "title": ["exact", "contains"],
            "status": ["exact"],
            "created_by": ["exact"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Chapter's filterset
class ChapterFilter(django_filters.FilterSet):
    class Meta:
        model = Chapter
        fields = {
            "id": ["exact"],
            "title": ["exact", "contains"],
            "curriculum": ["exact"],
            "order": ["exact", "gt", "lt"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Lesson's filterset
class LessonFilter(django_filters.FilterSet):
    class Meta:
        model = Lesson
        fields = {
            "id": ["exact"],
            "title": ["exact", "contains"],
            "chapter": ["exact"],
            "order": ["exact", "gt", "lt"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Assessment's filterset
class AssessmentFilter(django_filters.FilterSet):
    class Meta:
        model = Assessment
        fields = {
            "id": ["exact"],
            "type": ["exact"],
            "chapter": ["exact"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Enrollment's filterset
class EnrollmentFilter(django_filters.FilterSet):
    class Meta:
        model = Enrollment
        fields = {
            "id": ["exact"],
            "trainee": ["exact"],
            "curriculum": ["exact"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Note's filterset
class NoteFilter(django_filters.FilterSet):
    class Meta:
        model = Note
        fields = {
            "id": ["exact"],
            "lesson": ["exact"],
            "chapter": ["exact"],
            "trainer": ["exact"],
            "trainee": ["exact"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Feedback's filterset
class FeedbackFilter(django_filters.FilterSet):
    class Meta:
        model = Feedback
        fields = {
            "id": ["exact"],
            "curriculum": ["exact"],
            "trainee": ["exact"],
            "rating": ["exact", "gt", "lt"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Materials' filterset
class MaterialsFilter(django_filters.FilterSet):
    class Meta:
        model = Materials
        fields = {
            "id": ["exact"],
            "lesson": ["exact"],
            "type": ["exact"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }


# Evaluation's filterset
class EvaluationFilter(django_filters.FilterSet):
    class Meta:
        model = Evaluation
        fields = {
            "id": ["exact"],
            "score": ["exact", "gt", "lt"],
            "feedback": ["exact", "contains"],
            "title": ["exact", "contains"],
            "created_at": ["exact", "gt", "lt"],
            "is_deleted": ["exact"],
        }
