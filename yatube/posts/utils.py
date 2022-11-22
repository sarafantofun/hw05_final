from django.conf import settings
from django.core.paginator import Paginator


def get_page_obj(queryset, request):
    paginator = Paginator(queryset, settings.NUM_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return page_obj
