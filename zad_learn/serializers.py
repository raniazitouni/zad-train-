from rest_framework import serializers
from django.contrib.auth import get_user_model
# from core.serializers import CustomUserSerializer
from .models import (
    Trainer, Trainee, Curriculum, Chapter, Lesson,
    Enrollment, Evaluation, Assessment, Materials,
    Note, Question, Feedback, TraineeCurriculumProgress,
    ChatConversation, ChatMessage, TraineeAnswer
)

User = get_user_model()


class TrainerSerializer(serializers.ModelSerializer):
    """Serializer for Trainer model with user details."""
    # user = CustomUserSerializer(read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    created_curriculums = serializers.SerializerMethodField()

    class Meta:
        model = Trainer
        fields = [
            'id', 'bio', 'profession', 'specialization', 
            'years_of_experience', 'certifications', 'created_curriculums',
            'created_at', 'updated_at', 'is_deleted',
            'user_id', 'first_name', 'last_name','email'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_created_curriculums(self, obj) -> list:
        """Get all curriculums created by the trainer."""
        curriculums = Curriculum.objects.filter(
            created_by=obj, is_deleted=False
        ).values(
            "id", "title", "description", "status", "created_at", "updated_at"
        )
        return list(curriculums)


class TraineeSerializer(serializers.ModelSerializer):
    """Serializer for Trainee model with user details and enrollments."""
    # user = CustomUserSerializer(read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    enrolled_curriculums = serializers.SerializerMethodField()

    class Meta:
        model = Trainee
        fields = [
            'id','enrolled_curriculums',
            'created_at', 'updated_at', 'is_deleted',
            'user_id',  'first_name', 'last_name', 'email'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_enrolled_curriculums(self, obj) -> list:
        enrollments = Enrollment.objects.filter(trainee=obj, is_deleted=False)
        return EnrollmentSerializer(enrollments, many=True).data


class CurriculumSerializer(serializers.ModelSerializer):
    """Serializer for Curriculum model with trainer details."""
    trainer_id = serializers.IntegerField(source='created_by.id', read_only=True) 
    trainer_name = serializers.SerializerMethodField()
    chapter_count = serializers.SerializerMethodField()
    enrollment_count = serializers.SerializerMethodField()

    class Meta:
        model = Curriculum
        fields = [
            'id', 'title', 'description', 'thumbnail_url',
            'status', 'chapter_count', 'enrollment_count', 
            'created_at', 'updated_at', 'is_deleted',
            'trainer_id', 'trainer_name'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_trainer_name(self, obj) -> str:
        """Return the trainer's ID and full name."""
        if obj.created_by:
            return f"{obj.created_by.user.first_name} {obj.created_by.user.last_name}"
        
        return None

    def get_chapter_count(self, obj) -> int: 
        return obj.chapters.filter(is_deleted=False).count()

    def get_enrollment_count(self, obj) -> int:
        return obj.enrollments.filter(is_deleted=False).count()


class ChapterSerializer(serializers.ModelSerializer):
    """Serializer for chapter model with lesson count."""
    curriculum_id = serializers.IntegerField(source='curriculum.id', read_only=True)
    curriculum_title = serializers.CharField(source='curriculum.title', read_only=True)
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = [
            'id', 'title', 'description', 'order', 'objectives',
            'lesson_count', 'created_at', 'updated_at', 'is_deleted',
            'curriculum_id', 'curriculum_title'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_lesson_count(self, obj) -> int:
        return obj.lessons.filter(is_deleted=False).count()

class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for Question model with assessment details."""
    assessment_id = serializers.IntegerField(source='assessment.id', read_only=True)
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'type', 'text', 'options', 
                'correct_answer', 'order', 'created_at', 'updated_at',
                'assessment_id', 'assessment_title'
                ]
        read_only_fields = ['created_at', 'updated_at']


class AssessmentSerializer(serializers.ModelSerializer):
    """Serializer for Assessment model."""
    curriculum_id = serializers.IntegerField(source='chapter.curriculum.id', read_only=True)
    curriculum_title = serializers.CharField(source='chapter.curriculum.title', read_only=True)
    chapter_id = serializers.IntegerField(source='chapter.id', read_only=True)
    chapter_title = serializers.CharField(source='chapter.title', read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)


    class Meta:
        model = Assessment
        fields = [
            'id',  'type','title',
            'description', 'duration_minutes', 'passing_marks', 'max_attempts',
            'is_published', 'questions', 'created_at', 'updated_at', 'is_deleted',
            'curriculum_id', 'curriculum_title', 'chapter_id', 'chapter_title'

        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if not self.context.get('with_questions', True):
            rep.pop('questions', None)
        return rep


class MaterialsSerializer(serializers.ModelSerializer):
    """Serializer for material model."""
    lesson_id = serializers.IntegerField(source='lesson.id', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)

    class Meta:
        model = Materials
        fields = [
            'id', 'type', 'title', 'description',
            'url', 'file_size', 'file_type', 'json_data',
            'created_at', 'updated_at', 'is_deleted',
            'lesson_id', 'lesson_title'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LessonSerializer(serializers.ModelSerializer):
    """Serializer for Lesson model with content information."""
    chapter_id = serializers.IntegerField(source='chapter.id', read_only=True)
    curriculum_id = serializers.IntegerField(source='chapter.curriculum.id', read_only=True)
    curriculum_title = serializers.CharField(source='chapter.curriculum.title', read_only=True)
    chapter_title = serializers.CharField(source='chapter.title', read_only=True)
    materials = MaterialsSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'content',
            'order', 'duration_minutes', 'materials',
            'created_at', 'updated_at', 'is_deleted', 
            'curriculum_id', 'curriculum_title',
            'chapter_id', 'chapter_title'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Only include materials if requested
        if not self.context.get('with_materials', True):
            rep.pop('materials', None)
        return rep


class EvaluationSerializer(serializers.ModelSerializer):
    """Serializer for Evaluation model."""
    class Meta:
        model = Evaluation
        fields = [
            'id', 'title', 'score', 'feedback',
            'created_at', 'updated_at', 'is_deleted'        
        ]
        read_only_fields = ['created_at', 'updated_at']


class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for Enrollment model with user and curriculum details."""
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)
    trainee_name = serializers.SerializerMethodField()
    curriculum_id = serializers.IntegerField(source='curriculum.id', read_only=True)
    curriculum_title = serializers.CharField(source='curriculum.title', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 
            'created_at', 'updated_at', 'is_deleted', 
            'trainee_id', 'trainee_name', 'curriculum_id', 'curriculum_title'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_trainee_name(self, obj) -> str:
        """Return the trainer's ID and full name."""
        if obj.trainee:
            return f"{obj.trainee.user.first_name} {obj.trainee.user.last_name}"

        return None


class NoteSerializer(serializers.ModelSerializer):
    """Serializer for CurriculumAdvice model with trainer details."""
    curriculum_id = serializers.IntegerField(source='curriculum.id', read_only=True)
    curriculum_title = serializers.CharField(source='curriculum.title', read_only=True)
    trainer_id = serializers.IntegerField(source='trainer.id', read_only=True)
    trainer_name = serializers.SerializerMethodField()
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)
    trainee_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content',
            'is_public', 'created_at', 'updated_at', 'is_deleted',
            'curriculum_id', 'curriculum_title', 'trainer_id', 'trainer_name',
            'trainee_id', 'trainee_name'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            if hasattr(request.user, 'trainer'):
                validated_data['trainer'] = request.user.trainer
            elif hasattr(request.user, 'trainee'):
                validated_data['trainee'] = request.user.trainee
        return super().create(validated_data)
    
    def get_trainer_name(self, obj) -> str:
        """Return the trainer's ID and full name."""
        if obj.trainer:
            return f"{obj.trainer.user.first_name} {obj.trainer.user.last_name}"

        return None
    
    def get_trainee_name(self, obj) -> str:
        """Return the trainee's ID and full name."""
        if obj.trainee:
            return f"{obj.trainee.user.first_name} {obj.trainee.user.last_name}"

        return None
    



class TraineeAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraineeAnswer
        fields = '__all__'

class FeedbackSerializer(serializers.ModelSerializer):
    """Serializer for Feedback model with curriculum and trainee details."""
    curriculum_id = serializers.IntegerField(source='curriculum.id', read_only=True)
    curriculum_title = serializers.CharField(source='curriculum.title', read_only=True)
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)
    trainee_name = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = ['id', 'lessons_feedback', 'rating', 'comment', 'created_at', 'updated_at',
                'curriculum_id', 'curriculum_title', 'trainee_id', 'trainee_name'
                ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_trainee_name(self, obj) -> str:
        """Return the trainee's ID and full name."""
        if obj.trainee:
            return f"{obj.trainee.user.first_name} {obj.trainee.user.last_name}"

        return None


class TraineeCurriculumProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraineeCurriculumProgress
        fields = '__all__'


class ChatConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for ChatConversation model.
    """
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_name = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 
            'message_count', 'last_message', 'last_message_at',
            'created_at', 'updated_at', 'is_deleted',
            'user_id', 'user_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_message_at']

    def get_user_name(self, obj) -> str:
        """Return the user's full name."""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return None

    def get_message_count(self, obj) -> int:
        """Return the number of messages in the conversation."""
        return obj.messages.filter(is_deleted=False).count()

    def get_last_message(self, obj) -> dict:
        """Return the last message in the conversation."""
        last_message = obj.messages.filter(
            is_deleted=False
        ).order_by('-created_at').first()
        
        if last_message:
            return {
                'text': last_message.text,
                'sender': last_message.sender,
                'created_at': last_message.created_at
            }
        return None


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for ChatMessage model.
    """
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True)
    conversation_title = serializers.CharField(source='conversation.title', read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id','text', 'image_url',
            'image_description', 'sender', 
            'metadata', 'created_at', 'updated_at', 'is_deleted',
            'conversation_id', 'conversation_title'
        ]
        read_only_fields = ['created_at', 'updated_at']