import singer
from asana.error import ForbiddenError
from tap_asana.context import Context
from tap_asana.streams.base import Stream

LOGGER = singer.get_logger()


class Stories(Stream):
    name = "stories"
    replication_method = "INCREMENTAL"
    replication_key = "created_at"

    fields = [
        "gid",
        "resource_type",
        "created_at",
        "created_by",
        "created_by.name",
        "resource_subtype",
        "text",
        "html_text",
        "is_pinned",
        "assignee",
        "dependency",
        "duplicate_of",
        "duplicated_from",
        "follower",
        "hearted",
        "hearts",
        "is_edited",
        "liked",
        "likes",
        "new_approval_status",
        "new_dates",
        "new_enum_value",
        "new_name",
        "new_number_value",
        "new_resource_subtype",
        "new_section",
        "new_text_value",
        "num_hearts",
        "num_likes",
        "old_approval_status",
        "old_dates",
        "old_enum_value",
        "old_name",
        "old_number_value",
        "old_resource_subtype",
        "old_section",
        "old_text_value",
        "preview",
        "project",
        "source",
        "story",
        "tag",
        "target",
        "task",
    ]

    # Fields that require project_sections:read scope
    section_fields = ["new_section", "old_section"]
    _exclude_section_fields = False

    def get_opt_fields(self):
        """Get the opt_fields string, excluding section fields if needed."""
        fields = self.fields
        if self._exclude_section_fields:
            fields = [f for f in fields if f not in self.section_fields]
        return ",".join(fields)

    def get_stories_for_task(self, task_gid, opt_fields):
        """
        Fetch stories for a task, with automatic retry excluding section fields
        if we encounter a ForbiddenError due to missing project_sections:read scope.
        """
        try:
            for story in Context.asana.client.stories.get_stories_for_task(
                task_gid=task_gid,
                opt_fields=opt_fields,
                timeout=self.request_timeout,
            ):
                yield story
        except ForbiddenError as e:
            error_message = str(e)
            if "project_sections:read" in error_message and not self._exclude_section_fields:
                LOGGER.warning(
                    "Missing project_sections:read scope. "
                    f"Retrying without section fields ({self.section_fields})."
                )
                self._exclude_section_fields = True
                # Retry with updated opt_fields
                new_opt_fields = self.get_opt_fields()
                for story in Context.asana.client.stories.get_stories_for_task(
                    task_gid=task_gid,
                    opt_fields=new_opt_fields,
                    timeout=self.request_timeout,
                ):
                    yield story
            else:
                raise

    def get_objects(self):
        bookmark = self.get_bookmark()
        session_bookmark = bookmark

        # list of project ids
        project_ids = []

        for workspace in self.call_api("workspaces"):
            for team in self.call_api("teams", workspace=workspace["gid"]):
                for project in self.call_api("projects",
                                             workspace=workspace["gid"],
                                             team=team["gid"]
                                             ):
                    project_ids.append(project["gid"])

        # iterate over all project ids and continue fetching
        for project_id in project_ids:
            for task in self.call_api("tasks", project=project_id):
                task_gid = task.get("gid")
                # Use get_opt_fields() to get current fields (may have changed after first error)
                current_opt_fields = self.get_opt_fields()
                for story in self.get_stories_for_task(task_gid, current_opt_fields):
                    session_bookmark = self.get_updated_session_bookmark(
                        session_bookmark, story[self.replication_key]
                    )
                    if self.is_bookmark_old(story[self.replication_key]):
                        yield story

        self.update_bookmark(session_bookmark)


Context.stream_objects["stories"] = Stories
