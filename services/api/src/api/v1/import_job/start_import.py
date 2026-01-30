"""Start import endpoint."""

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.user import User
from utils.tasks.import_tasks.parse_source_task import parse_source_task


class StartImport(Endpoint):
    """Start a new recipe import job."""

    def execute(self, book_id: str, params: "StartImport.Params"):
        """
        Start a new import job for the recipe book.

        Args:
            book_id: The recipe book ID to import into.
            params: Import parameters including source type and URLs.

        Returns:
            Created import job data.
        """
        user: User = self.user

        # Check access - must be owner or editor
        membership = self.database.find_by(
            RecipeBookUser,
            user_id=user.id,
            recipe_book_id=book_id,
        )
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to import recipes to this book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

        # Verify recipe book exists
        recipe_book = self.database.find_by(RecipeBook, id=book_id)
        if not recipe_book:
            raise APIException(
                status_code=404,
                detail=f"Recipe book with ID '{book_id}' not found",
                code=ErrorCode.RECIPE_BOOK_NOT_FOUND,
            )

        # Validate input based on source type
        if params.source_type == "url":
            if not params.url:
                raise APIException(
                    status_code=400,
                    detail="URL is required for url source type",
                    code=ErrorCode.INVALID_REQUEST,
                )
            source_filename = params.url
        elif params.source_type == "url_list":
            if not params.urls or len(params.urls) == 0:
                raise APIException(
                    status_code=400,
                    detail="URLs are required for url_list source type",
                    code=ErrorCode.INVALID_REQUEST,
                )
            source_filename = None
        else:
            raise APIException(
                status_code=400,
                detail=f"Unsupported source type: {params.source_type}",
                code=ErrorCode.IMPORT_INVALID_SOURCE_TYPE,
            )

        # Create import job
        job = ImportJob(
            status="pending",
            source_type=params.source_type,
            source_filename=source_filename,
            user_id=user.id,
            recipe_book_id=book_id,
        )
        self.database.create(job)
        self.database.db.refresh(job)

        # Create import items for URL list
        if params.source_type == "url_list" and params.urls:
            for idx, url in enumerate(params.urls):
                item = ImportItem(
                    import_job_id=job.id,
                    source_type="url",
                    source_reference=str(idx + 1),
                    source_url=url,
                    status="pending",
                )
                self.database.create(item)
            job.total_items = len(params.urls)
            self.database.db.commit()
        elif params.source_type == "url":
            item = ImportItem(
                import_job_id=job.id,
                source_type="url",
                source_url=params.url,
                status="pending",
            )
            self.database.create(item)
            job.total_items = 1
            self.database.db.commit()

        # Dispatch background processing
        parse_source_task.delay(
            import_job_id=str(job.id),
            user_id=str(user.id),
        )

        return success(
            data=StartImport.Response(
                id=str(job.id),
                status=job.status,
                source_type=job.source_type,
                total_items=job.total_items,
                recipe_book_id=str(job.recipe_book_id),
                created_at=job.created_at,
            ),
            status=201,
        )

    class Params(BaseModel):
        source_type: str
        urls: list[str] | None = None
        url: str | None = None

    class Response(BaseModel):
        id: str
        status: str
        source_type: str
        total_items: int
        recipe_book_id: str
        created_at: str
