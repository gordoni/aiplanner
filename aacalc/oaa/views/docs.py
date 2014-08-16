from django.http import Http404
from django.shortcuts import render
from django.template.base import TemplateDoesNotExist

def docs(request, doc):
    assert(".." not in doc)
    try:
        return render(request, 'docs/' + doc + '.html')
    except TemplateDoesNotExist:
        raise Http404
