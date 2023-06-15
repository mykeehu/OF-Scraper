r"""
                                                             
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import time
import asyncio
from ofscraper.utils.semaphoreDelayed import semaphoreDelayed
import logging
import contextvars
import math
import httpx
from tenacity import retry,stop_after_attempt,wait_random
from rich.progress import Progress
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn
)
from rich.panel import Panel
from rich.console import Group
from rich.live import Live
from rich.style import Style
import arrow
import ofscraper.constants as constants
from ..utils import auth
import ofscraper.utils.console as console
import ofscraper.utils.args as args_

log=logging.getLogger(__package__)
attempt = contextvars.ContextVar("attempt")

sem = semaphoreDelayed(constants.AlT_SEM)
@retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True)   
async def scrape_pinned_posts(headers, model_id,progress, timestamp=None,required_ids=None) -> list:
    global tasks
    global sem
    posts=None
    attempt.set(attempt.get(0) + 1)
    if timestamp and   (float(timestamp)>(args_.getargs().before or arrow.now()).float_timestamp):
        return []
    if timestamp:
        log.debug(arrow.get(math.trunc(float(timestamp))))
        timestamp=str(timestamp)
        ep = constants.timelinePinnedNextEP
        url = ep.format(model_id, timestamp)
    else:
        ep=constants.timelinePinnedEP
        url=ep.format(model_id)
    log.debug(url)
    async with sem:
        task=progress.add_task(f"Attempt {attempt.get()}/{constants.NUM_TRIES}: Timestamp -> {arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}",visible=True)
        async with httpx.AsyncClient(http2=True, headers=headers) as c:
            auth.add_cookies(c)
            c.headers.update(auth.create_sign(url, headers))
            r = await c.get(url , timeout=None)
    if not r.is_error:
        progress.remove_task(task)
        posts = r.json()['list']
        if not posts:
            posts= []
        elif len(posts)==0:
            posts= []
        #post infinite loops            
        # elif required_ids==None:
        #     attempt.set(0)
            # tasks.append(asyncio.create_task(scrape_pinned_posts(headers, model_id,progress,timestamp=posts[0]['postedAtPrecise'])))
    else:
            log.debug(f"[bold]pinned request status code:[/bold]{r.status_code}")
            log.debug(f"[bold]pinned response:[/bold] {r.content.decode()}")
            log.debug(f"[bold]pinned headers:[/bold] {r.headers}")
            progress.remove_task(task)
            r.raise_for_status()
    return posts

async def get_pinned_post(headers,model_id): 
    overall_progress=Progress(SpinnerColumn(style=Style(color="blue")),TextColumn("Getting pinned media...\n{task.description}"))
    job_progress=Progress("{task.description}")
    progress_group = Group(
    overall_progress,
    Panel(Group(job_progress)))

    global tasks
    tasks=[]
    min_posts=50
    responseArray=[]
    page_count=0
    with Live(progress_group, refresh_per_second=5,console=console.shared_console): 

        tasks.append(asyncio.create_task(scrape_pinned_posts(headers,model_id,job_progress,timestamp=args_.getargs().float_timestamp if args_.getargs().after else None)))
    

        page_task = overall_progress.add_task(f' Pages Progress: {page_count}',visible=True)
        while len(tasks)!=0:
            for coro in asyncio.as_completed(tasks):
                result=await coro or []
                page_count=page_count+1
                overall_progress.update(page_task,description=f'Pages Progress: {page_count}')
                responseArray.extend(result)
            time.sleep(1)
            tasks=list(filter(lambda x:x.done()==False,tasks))
        overall_progress.remove_task(page_task)
    unduped=[]
    dupeSet=set()
    log.debug(f"[bold]Pinned Count with Dupes[/bold] {len(responseArray)} found")
    for post in responseArray:
        if post["id"] in dupeSet:
            continue
        dupeSet.add(post["id"])
        unduped.append(post)
    log.debug(f"[bold]Pinned Count without Dupes[/bold] {len(unduped)} found")
    return unduped                                
