from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .serializers import CustomUserDeleteSerializer  # Import your serializer
from rest_framework_simplejwt.tokens import RefreshToken
import logging
logger = logging.getLogger(__name__)


User = get_user_model()


def delete_tokens_for_user(user):
    """Deletes all refresh tokens (and implicitly access tokens) for a user."""
    try:
        RefreshToken.for_user(user).delete()
    except Exception as e:
        print(f"Error deleting tokens for user {user.id}: {e}")
        pass


class UserViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CustomUserDeleteSerializer

    @action(detail=False, methods=['delete'], url_path='delete')
    def delete_user(self, request):
        # Log the current user
        logger.info(f"Current user: {request.user}")

        # Use the serializer to validate input data
        serializer = self.serializer_class(data=request.data, context={'request': request})
        
        if serializer.is_valid(raise_exception=True):
            user = request.user
            
            # Delete tokens or perform any necessary clean-up
            delete_tokens_for_user(user)
            
            # Perform the deletion action
            user.delete()  # Ensure the user instance is deleted correctly
            
            return Response({"message": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
