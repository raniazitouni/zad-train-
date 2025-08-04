from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter
from django.urls import path, include
from . import views

# Initialize the main router
router = DefaultRouter()
router.register('trainers', views.TrainerViewSet)
router.register('trainees', views.TraineeViewSet)
router.register('curriculums', views.CurriculumViewSet)
router.register('evaluations', views.EvaluationViewSet, basename='evaluation')
router.register('materials', views.MaterialsViewSet, basename='material')
router.register('questions', views.QuestionViewSet, basename='question')
router.register(
    'trainee-answers',
    views.TraineeAnswerViewSet,
    basename='trainee-answer'
)
router.register(
    'trainee-progress',
    views.TraineeCurriculumProgressViewSet,
    basename='trainee-progress'
)
router.register(
    'enrollments',
    views.EnrollmentViewSet,
    basename='enrollment'
)
router.register(
    'feedbacks',
    views.FeedbackViewSet,
    basename='feedback'
)
router.register(
    'notes',
    views.NoteViewSet,
    basename='note'
)
router.register(
    r'chat-conversations',
    views.ChatConversationViewSet,
    basename='chat-conversation'
)
router.register(
    r'chat-messages',
    views.ChatMessageViewSet,
    basename='chat-message'
)

# Nested routers for curriculum-related materials
curriculums_router = NestedDefaultRouter(
    router,
    'curriculums',
    lookup='curriculum'
)

curriculums_router.register(
    'chapters',
    views.ChapterViewSet,
    basename='chapter'
)

# Nested routers for chapter-related materials
chapters_router = NestedDefaultRouter(
    curriculums_router,
    'chapters',
    lookup='chapter'
)
chapters_router.register(
    'assessments',
    views.AssessmentViewSet,
    basename='chapter-assessments'
)
chapters_router.register(
    'lessons',
    views.LessonViewSet,
    basename='chapter-lessons'
)

# Define the app name
app_name = 'zad_learn'

# Combine all urlpatterns
urlpatterns = [
    path('', include(router.urls)),
    path('', include(curriculums_router.urls)),
    path('', include(chapters_router.urls)),
]