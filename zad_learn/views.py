import requests
import time
import json
import threading
import logging
from  django.conf import settings 

from rest_framework import status, filters
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action, renderer_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, IsAuthenticated
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema

from django.http import StreamingHttpResponse
from django.db import transaction

from .models import (
    Trainer, Trainee, Curriculum, Chapter, Lesson,
    Enrollment, Evaluation, Assessment,
    Question, Note, Feedback, Materials, TraineeCurriculumProgress,
    ChatConversation, ChatMessage, TraineeAnswer
)
from .serializers import (
    TrainerSerializer, TraineeSerializer, CurriculumSerializer,
    ChapterSerializer, LessonSerializer, EnrollmentSerializer,
    EvaluationSerializer, AssessmentSerializer, MaterialsSerializer,
    QuestionSerializer, NoteSerializer, FeedbackSerializer, TraineeCurriculumProgressSerializer,
    ChatConversationSerializer, ChatMessageSerializer, TraineeAnswerSerializer
)
from .filters import CurriculumFilter, ChapterFilter, LessonFilter, AssessmentFilter, EnrollmentFilter, NoteFilter, FeedbackFilter, MaterialsFilter, EvaluationFilter
from .helpers.chat_utils import get_history_for_ai
from .helpers.utils import upload_to_s3 
from .helpers.curriculum_upsert import upsert_curriculum

logger = logging.getLogger(__name__)


class TrainerViewSet(ModelViewSet):
    """
    ViewSet for managing trainer profiles.
    Provides CRUD operations for trainers.
    """
    queryset = Trainer.objects.filter(is_deleted=False)
    serializer_class = TrainerSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a new trainer profile."""
        user_id = self.request.user.id
        logger.info(f"Creating trainer profile for user {user_id}")
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def curriculums(self, request, pk=None):
        """List all curriculums created by this trainer."""
        try:
            # Get the trainer object
            trainer = self.get_object()

            # Filter curriculums created by the trainer
            curriculums = Curriculum.objects.filter(
                created_by=trainer.user,
                is_deleted=False
            )

            # Serialize the curriculums
            serializer = CurriculumSerializer(curriculums, many=True, context={'request': request})

            # Return the serialized data
            return Response(serializer.data, status=200)

        except Trainer.DoesNotExist:
            # Handle case where the trainer does not exist
            return Response({"error": "Trainer not found."}, status=404)

        except Exception as e:
            # Handle any unexpected errors
            return Response({"error": str(e)}, status=500)


class TraineeViewSet(ModelViewSet):
    """
    ViewSet for managing trainee profiles.
    Provides CRUD operations and curriculum enrollment management.
    """
    queryset = Trainee.objects.filter(is_deleted=False)
    serializer_class = TraineeSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Create a new trainee profile."""
        user_id = self.request.user.id
        logger.info(f"Creating trainee profile for user {user_id}")
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def enrolled_curriculums(self, request, pk=None):
        """List all curriculums enrolled by this trainee."""
        trainee = self.get_object()
        enrollments = Enrollment.objects.filter(
            trainee=trainee,
            is_deleted=False
        )
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def enroll(self, request, pk=None):
        """Enroll the current trainee in a curriculum."""
        trainee = self.get_object()
        curriculum_id = request.data.get('curriculum_id')

        if not curriculum_id:
            return Response(
                {"detail": "curriculum_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            curriculum = Curriculum.objects.get(id=curriculum_id, is_deleted=False)
        except Curriculum.DoesNotExist:
            return Response(
                {"detail": "Curriculum not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if Enrollment.objects.filter(
            curriculum=curriculum,
            trainee=trainee,
            is_deleted=False
        ).exists():
            return Response(
                {"detail": "Already enrolled in this curriculum."},
                status=status.HTTP_400_BAD_REQUEST
            )

        enrollment = Enrollment.objects.create(
            curriculum=curriculum,
            trainee=trainee,
        )
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark_complete(self, request, pk=None):
        """
        Mark a lesson or assessment as completed for the current trainee and update their curriculum progress.
        This helps the trainee track their progress while attending lessons or passing assessments.
        """
        trainee = self.get_object()
        lesson_id = request.data.get('lesson_id')
        assessment_id = request.data.get('assessment_id')
        curriculum_id = request.data.get('curriculum_id')

        if not curriculum_id:
            return Response(
                {"detail": "curriculum_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            curriculum = Curriculum.objects.get(id=curriculum_id, is_deleted=False)
        except Curriculum.DoesNotExist:
            return Response(
                {"detail": "Curriculum not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only one of lesson_id or assessment_id should be provided
        obj = None
        obj_type = None
        obj_id = lesson_id or assessment_id
        if lesson_id:
            model = Lesson
            obj_type = 'lesson'
        elif assessment_id:
            model = Assessment
            obj_type = 'assessment'
        else:
            return Response(
                {"detail": "Either lesson_id or assessment_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            obj = model.objects.get(id=obj_id, is_deleted=False)
        except model.DoesNotExist:
            return Response(
                {"detail": f"{model.__name__} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Mark as completed for this trainee
        progress_kwargs = {
            'trainee': trainee,
            'curriculum': curriculum,
            obj_type: obj,
        }
        TraineeCurriculumProgress.objects.update_or_create(
            defaults={'is_completed': True},
            **progress_kwargs
        )
        logger.info(f"Trainee {trainee.id} marked {obj_type} {obj.id} as complete in curriculum {curriculum.id}")

        # Calculate progress percentage for the curriculum
        total_lessons = Lesson.objects.filter(chapter__curriculum=curriculum, is_deleted=False).count()
        total_assessments = Assessment.objects.filter(chapter__curriculum=curriculum, is_deleted=False).count()
        total_items = total_lessons + total_assessments

        completed_lessons = TraineeCurriculumProgress.objects.filter(
            trainee=trainee, curriculum=curriculum, lesson__isnull=False, is_completed=True
        ).count()
        completed_assessments = TraineeCurriculumProgress.objects.filter(
            trainee=trainee, curriculum=curriculum, assessment__isnull=False, is_completed=True
        ).count()
        completed_items = completed_lessons + completed_assessments

        progress_percentage = (completed_items / total_items) * 100 if total_items > 0 else 0

        return Response({
            'status': 'progress updated',
            'progress_percentage': progress_percentage,
            'completed_lessons': completed_lessons,
            'total_lessons': total_lessons,
            'completed_assessments': completed_assessments,
            'total_assessments': total_assessments
        })
    
    
    @action(detail=False, methods=['get'], url_path='progress-summary')
    def progress_summary(self, request):
        """
        Get list of answers and correctness percentage for a trainee,
        grouped by curriculum and chapter.
        Query params: trainee_id (required)
        """
        trainee_id = request.query_params.get('trainee_id')
        if not trainee_id:
            return Response({"detail": "trainee_id is required."}, status=400)

        # Get all answers for this trainee
        answers = TraineeAnswer.objects.filter(
            trainee_id=trainee_id,
            is_deleted=False
        ).select_related('question__assessment__chapter__curriculum', 'question')

        # Organize by curriculum and chapter
        summary = {}
        for ans in answers:
            curriculum = ans.question.assessment.chapter.curriculum
            chapter = ans.question.assessment.chapter

            cur_key = (curriculum.id, curriculum.title)
            chap_key = (chapter.id, chapter.title)

            if cur_key not in summary:
                summary[cur_key] = {}
            if chap_key not in summary[cur_key]:
                summary[cur_key][chap_key] = {
                    "answers": [],
                    "total": 0,
                    "correct": 0
                }

            summary[cur_key][chap_key]["answers"].append({
                "question_id": ans.question.id,
                "question_text": ans.question.text,
                "answer": ans.answer,
                "is_correct": ans.is_correct
            })
            summary[cur_key][chap_key]["total"] += 1
            if ans.is_correct:
                summary[cur_key][chap_key]["correct"] += 1

        # Format response
        result = []
        for (cur_id, cur_title), chapters in summary.items():
            chapters_list = []
            for (chap_id, chap_title), data in chapters.items():
                percent = (data["correct"] / data["total"] * 100) if data["total"] > 0 else 0
                chapters_list.append({
                    "chapter_id": chap_id,
                    "chapter_title": chap_title,
                    "correctness_percentage": percent,
                    "answers": data["answers"]
                })
            result.append({
                "curriculum_id": cur_id,
                "curriculum_title": cur_title,
                "chapters": chapters_list
            })

        return Response(result)

class CurriculumViewSet(ModelViewSet):
    """ViewSet for managing curriculums."""
    queryset = Curriculum.objects.filter(is_deleted=False)
    serializer_class = CurriculumSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CurriculumFilter
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title']

    def perform_create(self, serializer):
        """Create a new curriculum."""
        try:
            trainer = Trainer.objects.get(user=self.request.user)
            logger.info(f"Creating curriculum by trainer {trainer.id}")
            serializer.save(created_by=trainer)
        except Trainer.DoesNotExist:
            logger.error(f"User {self.request.user.id} is not associated with a trainer profile.")
            raise ValidationError("You must be a trainer to create a curriculum.")  

    @action(detail=False, methods=['post'], url_path='upsert')
    @transaction.atomic
    def upsert(self, request):
        data = request.data.get("curriculum")
        if not data:
            return Response({"detail": "Curriculum data is required."}, status=status.HTTP_400_BAD_REQUEST)
        return upsert_curriculum(data, request)

 

    @action(detail=False, methods=['get', 'post'], url_path='generate')
    @transaction.atomic
    def generate(self, request):
        """
        Generate a curriculum from an external service, then upsert it.
        Accepts optional POST data to send to the external service.
        """
        external_url = f"{settings.ZAD_TRAIN_CONTAINER}/curriculum/"
        if not settings.ZAD_TRAIN_CONTAINER:
            logger.error("ZAD_TRAIN_CONTAINER environment variable is not set!")
        try:
            # Allow sending data with POST, or just GET if no data
            if request.method == 'POST':
                ext_response = requests.post(external_url, json=request.data, timeout=30)
            else:
                ext_response = requests.get(external_url, timeout=30)
            ext_response.raise_for_status()
            try:
                ext_json = ext_response.json()
            except Exception as e:
                logger.error(f"Failed to decode JSON from external service: {str(e)}")
                return Response({"detail": "Invalid JSON from external service."}, status=status.HTTP_502_BAD_GATEWAY)

            curriculum_data = ext_json.get("curriculum")
            if not curriculum_data:
                logger.error(f"No curriculum returned from external service: {ext_json}")
                return Response(
                    {"detail": "No curriculum returned from external service.", "external_response": ext_json},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return upsert_curriculum(curriculum_data, request)
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error contacting external service: {str(e)}")
            return Response({"detail": f"Network error: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.error(f"Error generating curriculum: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
    @action(detail=True, methods=['get'], url_path='with-structure')
    def with_structure(self, request, pk=None):
        """
        Retrieve a curriculum with its chapters and, for each chapter, its lessons and assessments (no materials/questions).
        """
        try:
            curriculum = Curriculum.objects.get(pk=pk, is_deleted=False)
        except Curriculum.DoesNotExist:
            return Response({"detail": "Curriculum not found."}, status=404)

        curriculum_data = CurriculumSerializer(curriculum).data

        chapters = Chapter.objects.filter(curriculum=curriculum, is_deleted=False).order_by('order', 'id')
        chapters_list = []
        for chapter in chapters:
            chapter_data = ChapterSerializer(chapter).data

            # Get lessons and assessments for this chapter (basic info only)
            lessons = Lesson.objects.filter(chapter=chapter, is_deleted=False).order_by('order', 'id')
            assessments = Assessment.objects.filter(chapter=chapter, is_deleted=False).order_by('id')

            # Use only basic fields for lessons and assessments
            lesson_list = [
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "duration_minutes": lesson.duration_minutes,
                    "order": lesson.order,
                }
                for lesson in lessons
            ]
            assessment_list = [
                {
                    "id": assessment.id,
                    "title": assessment.title,
                    "type": assessment.type,
                    "order": assessment.order,
                }
                for assessment in assessments
            ]

            # Combine as "resources"
            resources = lesson_list + assessment_list
            # Optionally, sort by order if needed
            resources = sorted(resources, key=lambda x: x.get('order', 0))

            chapter_data['resources'] = resources
            chapters_list.append(chapter_data)

        curriculum_data['chapters'] = chapters_list
        return Response(curriculum_data)


class ChapterViewSet(ModelViewSet):
    """ViewSet for managing chapters within curriculums."""
    queryset = Chapter.objects.filter(is_deleted=False)
    serializer_class = ChapterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ChapterFilter
    ordering_fields = ['order']

    def get_queryset(self):
        """Filter chapters by curriculum if curriculum_pk is provided (for nested routes)."""
        queryset = Chapter.objects.filter(is_deleted=False)
        curriculum_pk = self.kwargs.get("curriculum_pk")
        if curriculum_pk:
            queryset = queryset.filter(curriculum_id=curriculum_pk)
        return queryset.order_by('-created_at')

    def get_serializer_context(self):
        """Pass curriculum_id to the serializer context."""
        context = super().get_serializer_context()
        context.update({
            "curriculum_id": self.kwargs.get("curriculum_pk")
        })
        return context

    @action(detail=True, methods=['GET'], url_path='get_resources')
    def get_resources(self, request, curriculum_pk=None, pk=None):
        """
        Retrieve all resources of a chapter, including lessons with their materials
        and assessments with their questions, using values() for performance.
        """
        try:
            chapter = Chapter.objects.filter(pk=pk, is_deleted=False).values(
                "id", "title", "description"
            ).first()
            if not chapter:
                return Response({"detail": "Chapter not found."}, status=404)
        except Exception:
            return Response({"detail": "Chapter not found."}, status=404)

        # Lessons and their materials
        lessons = list(
            Lesson.objects.filter(chapter_id=pk, is_deleted=False)
            .values("id", "title", "content")
        )
        lesson_ids = [lesson["id"] for lesson in lessons]
        materials = list(
            Materials.objects.filter(lesson_id__in=lesson_ids, is_deleted=False)
            .values(
                "id", "lesson_id", "type", "title", "url", "file_size", "file_type"
            )
        )
        # Map materials to lessons
        materials_map = {}
        for material in materials:
            materials_map.setdefault(material["lesson_id"], []).append({
                "id": material["id"],
                "type": material["type"],
                "title": material["title"],
                "url": material["url"],
                "file_size": material["file_size"],
                "file_type": material["file_type"],
            })
        for lesson in lessons:
            lesson["materials"] = materials_map.get(lesson["id"], [])

        # Assessments and their questions
        assessments = list(
            Assessment.objects.filter(chapter_id=pk, is_deleted=False)
            .values("id", "type", "title", "description")
        )
        assessment_ids = [a["id"] for a in assessments]
        questions = list(
            Question.objects.filter(assessment_id__in=assessment_ids)
            .values("id", "assessment_id", "text", "options", "correct_answer", "order")
        )
        # Map questions to assessments
        questions_map = {}
        for question in questions:
            questions_map.setdefault(question["assessment_id"], []).append({
                "id": question["id"],
                "text": question["text"],
                "options": question["options"],
                "correct_answer": question["correct_answer"],
                "order": question["order"]
            })
        for assessment in assessments:
            assessment["questions"] = questions_map.get(assessment["id"], [])

        data = {
            "chapter": 
            {
                **chapter,
                "lessons": lessons,
                "assessments": assessments
            }
            
        }
        return Response(data)

@extend_schema(parameters=[OpenApiParameter("curriculum_pk", type=int)])
class LessonViewSet(ModelViewSet):
    """ViewSet for managing lessons within chapters."""
    queryset = Lesson.objects.filter(is_deleted=False)
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = LessonFilter
    ordering_fields = ['order', 'created_at']

    def get_queryset(self):
        """Filter lessons by chapter if provided."""
        queryset = Lesson.objects.filter(is_deleted=False)
        chapter_pk = self.kwargs.get('chapter_pk', None)
        curriculum_pk = self.kwargs.get('curriculum_pk', None)
        if chapter_pk and curriculum_pk:
            queryset = queryset.filter(chapter_id=chapter_pk, chapter__curriculum_id=curriculum_pk)
        return queryset.order_by('order')
    
    def get_serializer_context(self):
        """Pass chapter_id to the serializer context."""
        context = super().get_serializer_context()
        required_kwargs = ["chapter_pk", "curriculum_pk"]
        
        if not all(kwargs in self.kwargs for kwargs in required_kwargs):
            raise ValueError("Missing required kwargs")
        context.update({
            "chapter_id": self.kwargs["chapter_pk"],
            "curriculum_id": self.kwargs["curriculum_pk"],
            "with_materials": self.request.query_params.get('with_materials', 'true').lower() == 'true'
        })

        return context

@extend_schema(parameters=[OpenApiParameter("curriculum_pk", type=int)])
class AssessmentViewSet(ModelViewSet):
    """ViewSet for managing assessments."""
    queryset = Assessment.objects.filter(is_deleted=False)
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AssessmentFilter
    ordering_fields = ['created_at']

    def get_queryset(self):
        """Filter assessments by chapter if provided."""
        queryset = Assessment.objects.filter(is_deleted=False)
        chapter_pk = self.kwargs.get('chapter_pk', None)
        curriculum_pk = self.kwargs.get('curriculum_pk', None)
        if chapter_pk and curriculum_pk:
            queryset = queryset.filter(chapter_id=chapter_pk, chapter__curriculum_id=curriculum_pk)
        return queryset.order_by('created_at')
    
    def get_serializer_context(self):
        """Pass chapter_id to the serializer context."""
        context = super().get_serializer_context()
        required_kwargs = ["chapter_pk", "curriculum_pk"]
        
        if not all(kwargs in self.kwargs for kwargs in required_kwargs):
            raise ValueError("Missing required kwargs")
        context.update({
            "chapter_id": self.kwargs["chapter_pk"],
            "curriculum_id": self.kwargs["curriculum_pk"],
            "with_quetions": self.request.query_params.get('with_quetions', 'true').lower() == 'true'
        })
        return context


class EvaluationViewSet(ModelViewSet):
    """ViewSet for managing lesson evaluations."""
    queryset = Evaluation.objects.filter(is_deleted=False)
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = EvaluationFilter
    ordering_fields = ['created_at', 'score']


class EnrollmentViewSet(ModelViewSet):
    """ViewSet for managing curriculum enrollments."""
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = EnrollmentFilter
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        """Ensure that only a trainee can create an enrollment."""
        try:
            # Check if the user is associated with a Trainee profile
            trainee = Trainee.objects.get(user=self.request.user)
            logger.info(f"Creating enrollment for trainee {trainee.id}")
            serializer.save(trainee=trainee)
        except Trainee.DoesNotExist:
            # Log and raise an error if the user is not a trainee
            logger.error(f"User {self.request.user.id} is not associated with a trainee profile.")
            raise ValidationError("You must be a trainee to create an enrollment.")

    def get_queryset(self):
        """Filter enrollments by user."""
        return Enrollment.objects.filter(
            trainee__user=self.request.user,
            is_deleted=False
        )


class QuestionViewSet(ModelViewSet):
    """ViewSet for managing questions."""
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer


class NoteViewSet(ModelViewSet):
    """ViewSet for managing notes."""
    queryset = Note.objects.filter(is_deleted=False)
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = NoteFilter
    ordering_fields = ['created_at']

    def get_queryset(self):
        """Filter notes by user."""
        return Note.objects.filter(
            user=self.request.user,
            is_deleted=False
        )


class FeedbackViewSet(ModelViewSet):
    """ViewSet for managing feedback."""
    queryset = Feedback.objects.filter(is_deleted=False)
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = FeedbackFilter
    ordering_fields = ['created_at']

    def get_queryset(self):
        """Filter feedback by user."""
        return Feedback.objects.filter(
            trainee__user=self.request.user,
            is_deleted=False
        )


class MaterialsViewSet(ModelViewSet):
    """ViewSet for managing materials (images, videos, or files) for lessons."""
    queryset = Materials.objects.filter(is_deleted=False)
    serializer_class = MaterialsSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MaterialsFilter
    ordering_fields = ['created_at']

    def get_queryset(self):
        """Optionally filter materials by lesson ID."""
        queryset = super().get_queryset()
        lesson_id = self.request.query_params.get('lesson_id')
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        return queryset

    def create(self, request, *args, **kwargs):
        """Handle the creation of a material and upload it to S3."""
        lesson_id = request.data.get('lesson')
        material_type = request.data.get('type')
        file = request.FILES.get('file')

        # Validate required fields
        if not lesson_id or not material_type or not file:
            return Response(
                {"detail": "lesson, type, and file are required fields."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate the lesson
            lesson = Lesson.objects.filter(id=lesson_id, is_deleted=False).exists()
            if not lesson:
                return Response(
                    {"detail": "Lesson not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Upload the file to S3
            s3_path = f"v1/materials/{file.name}"
            s3_url = upload_to_s3(file, s3_path)

            # Save the material to the database
            material = Materials.objects.create(
                lesson_id=lesson_id,
                type=material_type,
                title=file.name,
                url=s3_url,
                file_size=file.size,
                file_type=file.content_type
            )

            # Serialize and return the created material
            serializer = self.get_serializer(material)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Lesson.DoesNotExist:
            return Response(
                {"detail": "Lesson not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error creating material: {str(e)}")
            return Response(
                {"detail": "An error occurred while uploading the material."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class TraineeAnswerViewSet(ModelViewSet):
    """
    ViewSet for managing trainee answers to assessment questions.
    """
    queryset = TraineeAnswer.objects.filter(is_deleted=False)
    serializer_class = TraineeAnswerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']

    @action(detail=False, methods=['post'], url_path='submit')
    @transaction.atomic
    def submit_answer(self, request):
        """
        Record a trainee's answer to a question in an assessment.
        Required fields: trainee_id, question_id, answer
        """
        trainee_id = request.data.get('trainee_id')
        question_id = request.data.get('question_id')
        answer = request.data.get('answer')

        if not all([trainee_id, question_id, answer]):
            return Response(
                {"detail": "trainee_id, question_id, and answer are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            trainee = Trainee.objects.get(id=trainee_id, is_deleted=False)
            question = Question.objects.get(id=question_id, is_deleted=False)
        except (Trainee.DoesNotExist, Question.DoesNotExist):
            return Response(
                {"detail": "Invalid trainee or question."},
                status=status.HTTP_404_NOT_FOUND
            )

        is_correct = False
        if hasattr(question, "correct_answer"):
            is_correct = answer.strip().lower() == str(question.correct_answer).strip().lower()

        trainee_answer, created = TraineeAnswer.objects.update_or_create(
            trainee=trainee,
            question=question,
            defaults={
                'answer': answer,
                'is_correct': is_correct
            }
        )

        serializer = self.get_serializer(trainee_answer)
        return Response({
            "created": created,
            "is_correct": is_correct,
            "trainee_answer": serializer.data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
class TraineeCurriculumProgressViewSet(ModelViewSet):
    """ViewSet for managing trainee curriculum progress."""
    queryset = TraineeCurriculumProgress.objects.filter(is_deleted=False)
    serializer_class = TraineeCurriculumProgressSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']

    @action(detail=False, methods=['get'], url_path='completed')
    def get_completed(self, request):
        """
        Get completed lessons and assessments for a specific trainee and curriculum.
        Query params: trainee_id, curriculum_id
        """
        trainee_id = request.query_params.get('trainee_id')
        curriculum_id = request.query_params.get('curriculum_id')

        if not trainee_id or not curriculum_id:
            return Response(
                {"detail": "trainee_id and curriculum_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Completed lessons
        completed_lessons = TraineeCurriculumProgress.objects.filter(
            trainee_id=trainee_id,
            curriculum_id=curriculum_id,
            lesson__isnull=False,
            is_completed=True,
            is_deleted=False
        ).select_related('lesson')

        lessons_data = [
            {
                "id": progress.lesson.id,
                "title": progress.lesson.title
            }
            for progress in completed_lessons if progress.lesson
        ]

        # Completed assessments
        completed_assessments = TraineeCurriculumProgress.objects.filter(
            trainee_id=trainee_id,
            curriculum_id=curriculum_id,
            assessment__isnull=False,
            is_completed=True,
            is_deleted=False
        ).select_related('assessment')

        assessments_data = [
            {
                "id": progress.assessment.id,
                "title": progress.assessment.title
            }
            for progress in completed_assessments if progress.assessment
        ]

        return Response({
            "completed_lessons": lessons_data,
            "completed_assessments": assessments_data
        })   

@extend_schema(parameters=[OpenApiParameter("id", type=int)])
class ChatConversationViewSet(ModelViewSet):
    """
    ViewSet for managing chat conversations.
    """
    serializer_class = ChatConversationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at', 'last_message_at']

    def perform_create(self, serializer):
        """Create a new conversation for the current user."""
        serializer.save(user=self.request.user)

    def get_queryset(self):
        """Return conversations for the current user."""
        # Prevent errors during schema generation (e.g., drf-spectacular)
        if getattr(self, "swagger_fake_view", False):
            return ChatConversation.objects.none()
        return ChatConversation.objects.filter(
            user=self.request.user,
            is_deleted=False
        )


    @action(detail=True, methods=['POST'], url_path='redirect')
    def redirect(self, request, pk=None):
        """
        Handle chat messages and redirect to AI service.
        """
        frontend_data = request.data
        
        if not frontend_data or not frontend_data.get('text'):
            return Response(
                {"detail": "Message text is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conversation = self.get_object()
        except ChatConversation.DoesNotExist:
            return Response(
                "Conversation not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        # Create user message
        message_data = {
            'conversation': conversation.id,
            'text': frontend_data.get('text'),
            'image_url': frontend_data.get('image_url'),
            'image_description': frontend_data.get('image_description'),
            'sender': ChatMessage.USER
        }
        
        serializer = ChatMessageSerializer(data=message_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_message = serializer.save()

        try:
            # Prepare chat history
            chat_history = get_history_for_ai(conversation.id)
            
            # Call AI service
            request_body = {
                'text': user_message.text,
                'image_url': user_message.image_url,
                'chat_history': chat_history
            }
            
            start_time = time.time()
            ai_response = requests.post(
                'http://host.docker.internal:5001/chat',
                json=request_body,
                timeout=50
            )
            elapsed_time = time.time() - start_time

            if ai_response.status_code == 200:
                response_data = ai_response.json()
                
                # Create AI response message
                ai_message_data = {
                    'conversation': conversation.id,
                    'text': response_data.get('text'),
                    'image_url': response_data.get('image_url'),
                    'image_description': response_data.get('image_description'),
                    'sender': ChatMessage.AI_AGENT,
                    'metadata': response_data.get('metadata', {})
                }
                
                ai_serializer = ChatMessageSerializer(data=ai_message_data)
                if not ai_serializer.is_valid():
                    return Response(ai_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                ai_message = ai_serializer.save()
                
                return Response({
                    'user_message': ChatMessageSerializer(user_message).data,
                    'ai_message': ChatMessageSerializer(ai_message).data,
                    'processing_time': elapsed_time
                })
            else:
                return Response(
                    f"Error: {ai_response.status_code}",
                    status=status.HTTP_400_BAD_REQUEST
                )

        except requests.exceptions.Timeout:
            logger.error("Request to AI service timed out.")
            return Response(
                "Request timed out. Please try again later.",
                status=status.HTTP_400_BAD_REQUEST
            )
        except requests.RequestException as e:
            logger.error(f"Error communicating with AI service: {str(e)}")
            return Response(
                f"Error: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )
        

    @action(detail=True, methods=['POST'], url_path='stream')
    def stream(self, request, pk=None):
        """
        Stream chat responses from AI service.
        """
        frontend_data = request.data

        if not frontend_data or not frontend_data.get('text'):
            return Response(
                {"detail": "Message text is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conversation = self.get_object()
        except ChatConversation.DoesNotExist:
            return Response(
                "Conversation not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        # Create user message
        message_data = {
            'conversation': conversation.id,
            'text': frontend_data.get('text'),
            'image_url': frontend_data.get('image_url'),
            'image_description': frontend_data.get('image_description'),
            'sender': ChatMessage.USER
        }

        serializer = ChatMessageSerializer(data=message_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message = serializer.save()

        # Prepare chat history
        chat_history = get_history_for_ai(conversation.id)

        # Prepare request body
        request_body = {
            'text': user_message.text,
            'image_url': user_message.image_url,
            'chat_history': chat_history
        }

        # Use StreamingHttpResponse for streaming communication
        response = StreamingHttpResponse(
            self.stream_response(
                request_body,
                conversation,
                user_message
            ),
            content_type="text/event-stream"
        )
        response["X-Accel-Buffering"] = "no"  # Disable buffering in nginx
        response["Cache-Control"] = "no-cache"  # Ensure clients don't cache the data
        return response

    def stream_response(self, request_body, conversation, user_message):
        """
        Stream response from AI service.
        """
        try:
            start_time = time.time()
            ai_response = requests.post(
                'http://host.docker.internal:5001/chat/stream',
                json=request_body,
                stream=True,
                timeout=70
            )

            if ai_response.status_code != 200:
                logger.error(
                    "AI service responded with status code: %d",
                    ai_response.status_code
                )
                yield f"data: Error: {ai_response.status_code}\n\n"
                return

            complete_buffer = ""
            first_chunk = True
            chunk_time = None

            for chunk in ai_response.iter_content(chunk_size=512):
                if chunk:
                    buffer = chunk.decode("utf-8")
                    if first_chunk:
                        chunk_time = time.time()
                        first_chunk_time = chunk_time - start_time
                        first_chunk = False

                    complete_buffer += buffer

                    while True:
                        start_index = complete_buffer.find("{")
                        end_index = complete_buffer.find("}", start_index)

                        if start_index != -1 and end_index != -1:
                            json_str = complete_buffer[start_index:end_index + 1]

                            try:
                                parsed_data = json.loads(json_str)
                                inner_data = parsed_data.get("data")

                                if inner_data:
                                    yield f"data: {inner_data}\n\n"

                                complete_buffer = complete_buffer[end_index + 1:].strip()
                            except json.JSONDecodeError:
                                break
                        else:
                            break

            # Save AI response in background
            threading.Thread(
                target=self.save_response_to_db,
                args=(complete_buffer, conversation, user_message)
            ).start()

        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON: %s", str(e))
            yield f"data: Error: Failed to decode JSON\n\n"

        except requests.exceptions.Timeout:
            logger.error("Request to AI service timed out.")
            yield f"data: Error: Request timed out. Please try again later.\n\n"

        except requests.RequestException as e:
            logger.error(f"Error communicating with AI service: {str(e)}")
            yield f"data: Error: {str(e)}\n\n"
@extend_schema(parameters=[OpenApiParameter("id", type=int)])
class ChatMessageViewSet(ModelViewSet):
    """
    ViewSet for managing chat messages.
    """
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at']

    def get_queryset(self):
        """Return messages for the current user's conversations."""
        if getattr(self, "swagger_fake_view", False):
            return ChatMessage.objects.none()
        return ChatMessage.objects.filter(
            conversation__user=self.request.user,
            is_deleted=False
        ).select_related('conversation')

    def create(self, request, *args, **kwargs):
        """
        Create a chat message. If an image is included, upload it to S3 first and store the URL.
        """
        data = request.data.copy()
        image_file = request.FILES.get('image', None)

        if image_file:
            # Validate file extension
            allowed_extensions = ['jpg', 'jpeg', 'png']
            file_extension = image_file.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                return Response(
                    {"detail": f"Invalid image extension. Allowed: {', '.join(allowed_extensions)}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Upload to S3
            s3_path = f"v1/chat-images/{image_file.name}"
            try:
                s3_url = upload_to_s3(image_file, s3_path)
                data['image_url'] = s3_url
            except Exception as e:
                logger.error(f"Error uploading chat image to S3: {str(e)}")
                return Response(
                    {"detail": "Failed to upload image."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            data['image_url'] = None

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)