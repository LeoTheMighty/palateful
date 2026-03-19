"""Recipe endpoint implementations."""

from api.v1.recipe.add_recipe_note import AddRecipeNote
from api.v1.recipe.bulk_archive_recipes import BulkArchiveRecipes
from api.v1.recipe.bulk_move_recipes import BulkMoveRecipes
from api.v1.recipe.bulk_update_tags import BulkUpdateTags
from api.v1.recipe.copy_recipe import CopyRecipe
from api.v1.recipe.fork_recipe import ForkRecipe
from api.v1.recipe.delete_recipe_note import DeleteRecipeNote
from api.v1.recipe.create_recipe import CreateRecipe
from api.v1.recipe.delete_recipe import DeleteRecipe
from api.v1.recipe.get_photo_upload_url import GetRecipePhotoUploadUrl
from api.v1.recipe.get_public_recipe import GetPublicRecipe
from api.v1.recipe.get_recipe import GetRecipe
from api.v1.recipe.get_recipe_version import GetRecipeVersion
from api.v1.recipe.get_recipe_versions import GetRecipeVersions
from api.v1.recipe.list_archived_recipes import ListArchivedRecipes
from api.v1.recipe.list_favorites import ListFavorites
from api.v1.recipe.list_recipes import ListRecipes
from api.v1.recipe.move_recipe import MoveRecipe
from api.v1.recipe.restore_recipe import RestoreRecipe
from api.v1.recipe.restore_recipe_version import RestoreRecipeVersion
from api.v1.recipe.toggle_favorite import ToggleFavorite
from api.v1.recipe.update_recipe import UpdateRecipe

__all__ = [
    "AddRecipeNote",
    "DeleteRecipeNote",
    "ListRecipes",
    "ListArchivedRecipes",
    "ListFavorites",
    "CreateRecipe",
    "CopyRecipe",
    "ForkRecipe",
    "BulkMoveRecipes",
    "BulkArchiveRecipes",
    "BulkUpdateTags",
    "GetRecipe",
    "GetRecipeVersion",
    "GetRecipeVersions",
    "GetPublicRecipe",
    "GetRecipePhotoUploadUrl",
    "MoveRecipe",
    "RestoreRecipe",
    "RestoreRecipeVersion",
    "ToggleFavorite",
    "UpdateRecipe",
    "DeleteRecipe",
]
