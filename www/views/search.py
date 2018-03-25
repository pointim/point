from point.app import search
from point.util.env import env
from geweb.template import render

import settings

def search_posts():
    search_text = env.request.args('text', '').strip().decode('utf-8')
    if not search_text:
        return render('/search.html', search_text='', page=1, results=[])

    try:
        page = int(env.request.args('page', 1))
    except ValueError:
        page = 1

    offset = (page - 1) * settings.page_limit

    user = env.owner if env.owner else None

    try:
        results, has_next, total = search.search_posts(search_text, user=user,
                           offset=offset, limit=settings.page_limit)

        return render('/search.html', search_text=search_text, results=results,
                      page=page, has_next=has_next, total=total)
    except:
        return render('/search-error.html')
