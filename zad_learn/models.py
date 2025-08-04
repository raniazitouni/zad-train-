from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.core.validators import FileExtensionValidator

from .core_models import TimestampedModel, SoftDeleteModel
from .helpers.utils import material_file_size


class Trainer(TimestampedModel, SoftDeleteModel):
    """
    Represents a trainer or tutor.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainer_profile'
    )
    profession = models.CharField(max_length=255, blank=True, null=True)
    specialization = models.CharField(max_length=255, blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(default=1)
    certifications = ArrayField(
        models.CharField(max_length=255), blank=True, null=True
    )
    bio = models.TextField(blank=True, null=True)


class Trainee(TimestampedModel, SoftDeleteModel):
    """
    Represents a trainee or learner.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainee_profile'
    )


class Curriculum(TimestampedModel, SoftDeleteModel):
    """
    Represents a course or curriculum.
    """
    title = models.CharField(max_length=255)
    description = models.TextField()
    thumbnail_url = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(
        'Trainer',
        on_delete=models.CASCADE,
        related_name='created_curriculums'
    )
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ]
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='published'
    )


class Chapter(TimestampedModel, SoftDeleteModel):
    """
    Represents a chapter within a curriculum.
    """
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name='chapters'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    objectives = ArrayField(
        models.CharField(max_length=255), blank=True, null=True
    )
    order = models.PositiveIntegerField(default=0)


class Lesson(TimestampedModel, SoftDeleteModel):
    """
    Represents a lesson within a chapter.
    """
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name='lessons'
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)


class Materials(TimestampedModel, SoftDeleteModel):
    """
    Represents a Materials (video, image, file) attached to a lesson.
    """
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='materials'
    )
    MATERIAL_TYPE_CHOICES = [
        ('video', 'Video'),
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('file', 'File'),
        ('json', 'JSON'),
    ]
    type = models.CharField(
        max_length=50,
        choices=MATERIAL_TYPE_CHOICES,
        default='video'
    )
    file = models.FileField(
        upload_to='v1/materials/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "doc", "docx", "txt", "jpg", "jpeg", "png", "mp4"]),
            material_file_size
        ]
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    file_type = models.CharField(max_length=100, blank=True, null=True)
    json_data = models.JSONField(blank=True, null=True)


class TraineeCurriculumProgress(TimestampedModel, SoftDeleteModel):
    """
    Tracks a trainee's progress through a curriculum.
    """
    trainee = models.ForeignKey(
        Trainee,
        on_delete=models.CASCADE,
        related_name='curriculum_progress'
    )
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name='trainee_progress'
    )
    completed_lessons = models.ManyToManyField(
        Lesson,
        related_name='completed_by'
    )
    completed_assessments = models.ManyToManyField(
        'Assessment',
        related_name='completed_by'
    )
    last_accessed = models.DateTimeField(auto_now=True)
    progress_status = models.CharField(
        max_length=50,
        choices=[
            ('not_started', 'Not Started'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='not_started'
    )
    progress_percentage = models.FloatField(default=0.0)


class Evaluation(TimestampedModel, SoftDeleteModel):
    """
    Represents an evaluation for a lesson.
    """
    progress = models.ForeignKey(
        TraineeCurriculumProgress,
        on_delete=models.SET_NULL,
        null=True,  # Allow null values for SET_NULL behavior
        related_name='evaluations'
    )
    score = models.FloatField(default=0.0)
    feedback = models.TextField(blank=True, null=True)
    title = models.CharField(max_length=255)


class Enrollment(TimestampedModel, SoftDeleteModel):
    """
    Represents a user's enrollment in a curriculum.
    """
    trainee = models.ForeignKey(
        'Trainee',
        on_delete=models.CASCADE,
        related_name='curriculum_enrollments'
    )
    curriculum = models.ForeignKey(
        'Curriculum',
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    class Meta:
        unique_together = ('trainee', 'curriculum')


class Assessment(TimestampedModel, SoftDeleteModel):
    """
    Represents a assessment for a chapter.
    """
    chapter = models.ForeignKey(
        'Chapter',
        on_delete=models.CASCADE,
        related_name='assessments'
    )
    type = models.CharField(
        max_length=50,
        choices=[
            ('quiz', 'Quiz'),
            ('assignment', 'Assignment'),
            ('exam', 'Exam'),
            ('project', 'Project')
        ]
    )
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    passing_marks = models.PositiveIntegerField(blank=True, null=True)
    max_attempts = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)


class Question(TimestampedModel, SoftDeleteModel):
    """
    Represents a question within an assessment.
    """
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('open-ended', 'Open-Ended')
    ]
    type = models.CharField(
        max_length=50,
        choices=QUESTION_TYPE_CHOICES
    )
    text = models.TextField()
    options = ArrayField(
        models.CharField(max_length=255), blank=True, null=True
    )
    correct_answer = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)


class TraineeAnswer(TimestampedModel, SoftDeleteModel):
    """
    Stores a trainee's answer to a specific question in an assessment.
    """
    trainee = models.ForeignKey(
        Trainee,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='trainee_answers'
    )
    answer = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('trainee', 'question')

class Note(TimestampedModel, SoftDeleteModel):
    """
    Represents notes or comments from a trainer or trainees in a specific
    lesson or chapter.
    """
    lesson = models.ForeignKey(  
        Lesson,
        on_delete=models.CASCADE,
        related_name='lessons_entries',
        blank=True,
        null=True
    )
    chapter = models.ForeignKey(  
        Chapter,
        on_delete=models.CASCADE,
        related_name='notes_entries',
        blank=True,
        null=True
    )
    trainer = models.ForeignKey(
        Trainer,
        on_delete=models.CASCADE,
        related_name='given_advice',
        blank=True,
        null=True
    )
    trainee = models.ForeignKey(
        Trainee,
        on_delete=models.CASCADE,
        related_name='notes',
        blank=True,
        null=True
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_public = models.BooleanField(
        default=True,
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.trainer and not self.trainee:
            raise ValidationError(
                "A note must be associated with either a trainer or a trainee."
            )
        if self.trainer and self.trainee:
            raise ValidationError(
                "A note cannot be associated with both a trainer and a trainee."
            )


class Feedback(TimestampedModel, SoftDeleteModel):
    """
    Represents feedback from a trainee about a curriculum.
    """
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name='feedback_entries'
    )
    trainee = models.ForeignKey(
        Trainee,
        on_delete=models.CASCADE,
        related_name='given_feedback'
    )
    lessons_feedback = models.JSONField(default=dict, blank=True)
    rating = models.PositiveIntegerField(default=0)
    comment = models.TextField(blank=True, null=True)


class ChatConversation(TimestampedModel, SoftDeleteModel):
    """
    Represents a chat conversation between a user and the AI.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations'
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    last_message_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Chat {self.id} - {self.title or 'Untitled'}"


class ChatMessage(TimestampedModel, SoftDeleteModel):
    """
    Represents a message in a chat conversation, supporting both text and images.
    """
    USER = "user"
    AI_AGENT = "ai"
    MESSAGE_SENDERS = [
        (USER, "user"),
        (AI_AGENT, "ai"),
    ]

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    text = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    image_description = models.TextField(blank=True, null=True)
    sender = models.CharField(max_length=9, choices=MESSAGE_SENDERS, default=USER)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.id} from {self.sender}"

    def save(self, *args, **kwargs):
        # Update the conversation's last_message_at when a new message is added
        self.conversation.last_message_at = timezone.now()
        self.conversation.save()
        super().save(*args, **kwargs)


# populate the database with the data from json file