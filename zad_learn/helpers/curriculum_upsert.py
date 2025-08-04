from rest_framework.response import Response
from rest_framework import status
from ..models import Curriculum, Chapter, Lesson, Assessment, Materials, Question, Trainer

import logging
logger = logging.getLogger(__name__)

def upsert_curriculum(data, request):
    # Check if the curriculum title already exists
    if Curriculum.objects.filter(title=data["title"], is_deleted=False).exists():
        return Response({"detail": "A curriculum with this title already exists."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        trainer = Trainer.objects.get(user=request.user)
        curriculum = Curriculum.objects.create(
            title=data["title"],
            description=data["description"],
            created_by=trainer
        )

        chapters_data = data.get("chapters", [])
        chapter_objs = []
        for idx, chapter_data in enumerate(chapters_data):
            chapter_objs.append(
                Chapter(
                    title=chapter_data["title"],
                    curriculum=curriculum,
                    description=chapter_data.get("description", ""),
                    objectives=chapter_data.get("objectives", []) 
                )
            )
        Chapter.objects.bulk_create(chapter_objs)
        chapters = list(Chapter.objects.filter(curriculum=curriculum).order_by('id'))
        chapter_map = {i: chapter for i, chapter in enumerate(chapters)}

        lesson_objs, lesson_parent = [], []
        assessment_objs, assessment_parent = [], []
        for idx, chapter_data in enumerate(chapters_data):
            for content_data in chapter_data.get("content", []):
                if content_data["type"] == "lesson":
                    lesson_objs.append(
                        Lesson(
                            title=content_data["title"],
                            chapter=chapter_map[idx],
                        #    content=content_data["content"]
                        )
                    )
                    lesson_parent.append((idx, content_data["title"]))
                elif content_data["type"] == "assessment":
                    assessment_objs.append(
                        Assessment(
                            chapter=chapter_map[idx],
                            type=content_data["assessmentType"],
                            title=content_data.get("title", ""),
                            description=content_data.get("description", "")
                        )
                    )
                    assessment_parent.append((idx, content_data.get("title", "")))

        Lesson.objects.bulk_create(lesson_objs)
        Assessment.objects.bulk_create(assessment_objs)
        lessons = list(Lesson.objects.filter(chapter__curriculum=curriculum).order_by('id'))
        assessments = list(Assessment.objects.filter(chapter__curriculum=curriculum).order_by('id'))

        lesson_map = {key: lesson for key, lesson in zip(lesson_parent, lessons)}
        assessment_map = {key: assessment for key, assessment in zip(assessment_parent, assessments)}

        material_objs, question_objs = [], []
        for idx, chapter_data in enumerate(chapters_data):
            for content_data in chapter_data.get("content", []):
                if content_data["type"] == "lesson":
                    lesson = lesson_map[(idx, content_data["title"])]
                    lesson_content = content_data.get("content")
                    
                    if isinstance(lesson_content, dict) and "slides" in lesson_content:
                        material_objs.append(
                            Materials(
                                lesson=lesson,
                                type="slides",
                                title=content_data["title"],
                                json_data=lesson_content["slides"]
                            )
                        )
                    
                    for resource in content_data.get("resources", []):
                        material_objs.append(
                            Materials(
                                lesson=lesson,
                                type=resource.get("type", "video"),
                                title=resource.get("title", ""),
                                url=resource.get("url", ""),
                                file_size=resource.get("file_size", 0),
                                file_type=resource.get("file_type", ""),
                                json_data=resource.get("content", {})
                            )
                        )
                elif content_data["type"] == "assessment":
                    assessment = assessment_map[(idx, content_data.get("title", ""))]
                    for question_data in content_data.get("questions", []):
                        question_objs.append(
                            Question(
                                assessment=assessment,
                                text=question_data.get("question", ""),
                                options=question_data.get("options", []),
                                correct_answer=question_data.get("answer", ""),
                                order=question_data.get("order", 0)
                            )
                        )
        Materials.objects.bulk_create(material_objs)
        Question.objects.bulk_create(question_objs)

        # Optionally, return the structure with IDs for each chapter and their nested elements
        response_chapters = []
        for idx, chapter in chapter_map.items():
            chapter_content = chapters_data[idx].get("content", [])
            lessons_list, assessments_list = [], []
            for content_data in chapter_content:
                if content_data["type"] == "lesson":
                    lesson = lesson_map[(idx, content_data["title"])]
                    lessons_list.append({
                        "id": lesson.id,
                        "title": lesson.title
                    })
                elif content_data["type"] == "assessment":
                    assessment = assessment_map[(idx, content_data.get("title", ""))]
                    assessments_list.append({
                        "id": assessment.id,
                        "title": assessment.title
                    })
            response_chapters.append({
                "id": chapter.id,
                "title": chapter.title,
                "lessons": lessons_list,
                "assessments": assessments_list
            })

        return Response({
            "detail": "Curriculum upserted successfully.",
            "id": curriculum.id,
            "title": curriculum.title,
            "description": curriculum.description,
            "created_by": curriculum.created_by.user.first_name + " " + curriculum.created_by.user.last_name,
            "created_at": curriculum.created_at,
            "chapters": response_chapters
        }, status=status.HTTP_201_CREATED)
    except Trainer.DoesNotExist:
        return Response({"detail": "Trainer not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error upserting curriculum: {str(e)}")
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)