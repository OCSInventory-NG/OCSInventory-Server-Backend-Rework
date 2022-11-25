from autoaction.tasks.views import TasksViewSet


class TasksRouter:
    """
    Router class is intended to define the route related to an app
    defineRoutes method need to be defined and called in main urls.py
    """

    @staticmethod
    def defineRoutes(defaultRouter):
        """
        This method will provide the routes related to the app and return the new routes

        Args:
            defaultRouter ([DefaultRouter]): Default router from main urls.py

        Returns:
            [DefaultRouter]: Updated router with app's dedicated routes
        """
        defaultRouter.register(r"tasks", TasksViewSet)
        return defaultRouter