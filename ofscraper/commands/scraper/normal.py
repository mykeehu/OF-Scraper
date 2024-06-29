import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.scraper.execute import execute_user_action
from ofscraper.commands.utils.wrappers.normal import get_user_action_function
from ofscraper.utils.context.run_async import run


@exit.exit_wrapper
@run
async def process_users_actions_normal(userdata=None, session=None):
    progress_utils.update_user_activity(description="Users with Actions Completed")
    return await get_user_action_function(execute_user_action)(userdata, session)