# projects/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from bson import ObjectId

from ..models.project_models import ProjectModel
from ..serializers.project_serializers import ProjectCreateSerializer, ProjectUpdateSerializer
from local.auth_app.permissions.decorators import require_permission

class ProjectListCreateView(APIView):
    @require_permission("view_projects")
    def get(self, request):
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 10))

        projects = ProjectModel.find_all(page=page, limit=limit)
        return Response(projects, status=status.HTTP_200_OK)

    @require_permission("create_project")
    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user_id = user.get("id", "")    # Assuming user is authenticated
            project = ProjectModel.create({**serializer.validated_data, "created_by": ObjectId(user_id)})
            return Response(project, status=status.HTTP_201_CREATED)
        return Response({ "error": serializer.errors }, status=status.HTTP_400_BAD_REQUEST)

class ProjectListView(APIView):
    @require_permission("view_projects")
    def get(self, request):
        projects = ProjectModel.fetch_names()
        return Response(projects, status=status.HTTP_200_OK)
    
class ProjectDetailView(APIView):
    @require_permission("view_projects")
    def get(self, request, project_id):
        project = ProjectModel.find_by_id(project_id)
        if not project:
            return Response({"error": "Project Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(project, status=status.HTTP_200_OK)

    @require_permission("update_project")
    def patch(self, request, project_id):
        project = ProjectModel.find_by_id(project_id)
        if not project:
            return Response({"error": "Project Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectUpdateSerializer(data=request.data)
        if serializer.is_valid():
            updated = ProjectModel.update(project_id, serializer.validated_data)
            return Response(updated, status=status.HTTP_202_ACCEPTED)
        return Response({ "error": serializer.errors }, status=status.HTTP_400_BAD_REQUEST)

    @require_permission("delete_project")
    def delete(self, request, project_id):
        ProjectModel.soft_delete(project_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
