"""
Created on Jul 2, 2015

@author: derigible

An attempt to combine views with a manager without having to write any extra
code. This is to make writing REST applications much simpler as it will
treat each table as if it is a returnable entity. The beauty of this setup
is that since it is a Django manager it can still be referenced by other 
Django models. This only adds some automatic support to the manager, nothing
more.
"""

from json import loads as load

from django.db import models as m
from django.views.generic.base import View
from django.http.response import HttpResponse
from django.core import serializers as sz


def err(msg, status = 400):
    '''
    Send an error response.
    
    @param msg: the reason for the error
    @param status: the status code of the error
    @return the HttpResponse object
    '''
    resp = HttpResponse('{{"err" : "{}"}}'.format(msg), content_type = "application/json", status = status)
    resp.reason_phrase = msg
    return resp
    
def read(request):
    '''
    Read and decode the payload.
    
    @param request: the request object to read
    @return the decoded request payload
    '''
    d = request.read()
    if d:
        try:
            d = load(d.decode('utf-8'))
        except ValueError as e:
            raise ValueError("Not a valid json object: {}".format(e))
    return d

class ViewWrapper(View):
    """
    A wrapper to ensure that the view class never gets positional arguments so
    as to make it work with being combined with Models.
    """
    register_route = False
    def __init__(self, *args, **kwargs):
        super(ViewWrapper, self).__init__(**kwargs)
        
    def dispatch(self, request, *args, **kwargs):
        #It makes sense why these are stored in the request, but i want them
        #in the view for convenience purposes
        self.accept = request.META.get('HTTP_ACCEPT', 'application/json')
        self.params = request.GET
        try:
            self.data = read(request)
        except ValueError as e:
            return err(e)
        return super(ViewWrapper, self).dispatch(request, *args, **kwargs)

class ModelAsView(m.Model, ViewWrapper):
    model_name = None   
    
    @property
    def m2ms(self):
        if not hasattr(self, "_m2ms"):
            self._m2ms = [str(m2m[0]).split('.')[-1] for m2m in self.__class__._meta.get_m2m_with_model()]
        return self._m2ms
    
    def _get_qs(self, *args, **kwargs):
        '''
        A helper method to get the queryset, to be used for GET, PUT, and maybe DELETE. Look at the
        GET docs to see how this works.
        '''
        args = args[0].split('/')[:-1]
        if not args:
            qs = self.__class__.objects.all()
            if "ids" in self.params:
                ids = self.params.get('ids').split(',')
                qs = qs.filter(id__in = ids)
            reqDict = {field : self.params[field] for field in self.__class__._meta.get_all_field_names() if field in self.params}
            return qs.filter(**reqDict)      
        elif len(args) == 1:
            return self.__class__.objects.filter(id = args[0])
        else:
            reqDict = {field : self.params[field] for field in self.__class__._meta.get_all_field_names() if field in self.params}
            return self.__class__.objects.filter(id__in = args, **reqDict)
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all entities. Otherwise, the args can come in two formats:
        
            1) the first arg in the path (passed in as a path variable) is an id of the entity
                a) filter args need to be passed in as query params
            2) add as many ids as you can in the path in this manner: /1/2/3/4/.../ 
            3) add the query param ids as a csv for those entities by id you want: ids=1,2,3,4,...
                
        Note that the query params need to match the name of the manager fields in order to work.
        '''
        qs = self._get_qs(*args, **kwargs)
        if self.params.get("expand", False):
            qs = qs.select_related().prefetch_related()
        return self.response(qs)
    
    def post(self, request, *args, **kwargs):
        '''
        The post currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "<m2m>" : [
                <m2m_id>,...
            ]
        }
        '''
        bp = self.__class__.objects.create(user = request.user, **self.data["data"])
        if len(self.data) > 1: #there are many2many fields to add, lets add them
            for m2m in self.m2ms: #Get the name of the m2m used
                if m2m in self.data and type(self.data.get(m2m)) == list:
                    getattr(bp, m2m).add(*self.data[m2m])
        return self.response((bp,))
    
    def put(self, request, *args, **kwargs):
        '''
        The put currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "add_<m2m>" : [
                <m2m_id>,...
            ],
            "delete_<m2m>" : [
                <m2m_id>,...
            ]
        }
        
        Note that you can update from a queryset relative to the rules of a get. Meaning you 
        can search for a set of entities to update at once.
        '''
        qs = self._get_qs(*args, **kwargs)
        if len(qs) > 1:
            return err("Can only update one entity at a time.")
        qs.update(**self.data["data"])
        if len(self.data) > 1: #there are many2many fields to add and delete, lets add them
            for m2m in self.m2ms:
                print(m2m)
                am2m = "add_" + m2m
                dm2m = "delete_" + m2m
                if am2m in self.data and type(self.data.get(am2m)) == list:
                    print("adding")
                    getattr(qs[0], m2m).add(*self.data[am2m])
                if dm2m in self.data and type(self.data.get(dm2m)) == list:
                    getattr(qs[0], m2m).remove(*self.data[dm2m])
        return self.other_response()
    
    def delete(self, request, *args, **kwargs):
        '''
        Delete an entity. This is a no payload endpoint where you can delete either in bulk by adding
        doing one of the three things:
        
            1) a single entity: .../entity/<id>/ where you just add one id in the path
            2) multiple entities: .../entity/<id>/<id2>/.../ where you add as many ids as you want in the path
            3) leave the args blank and add query param with at least one query param called ids as follows:
                
                    ids=1,2,3,4,5
                    
                note that the ids are a csv.
                
            Note that the GET argument can also be used to help narrow down from the list of ids those that
            contain other query attributes. Note that these query attributes need to have the names of the manager
            fields, just like in getting objects.
        '''
        args = args[0].split('/')[:-1]
        if not args:
            if "ids" not in self.params:
                return err("Did not contain any valid ids to delete.")
            ids = self.params.get("ids").split(',')
            reqDict = {field : self.params[field] 
                       for field in self.__class__._meta.get_all_field_names() 
                       if field in self.params}
            deletes = self.__class__.objects.filter(id__in = ids, **reqDict)
        elif len(args) == 1:
            deletes = self.__class__.objects.get(id = args[0])
        else:
            deletes = self.__class__.objects.filter(id__in = args)
        
        deletes.delete()
        
        return self.other_response()
    
    def set_headers(self, response, headers):
        '''
        Set a dictionary of headers to the HttpResponse object.
        
        @param response: the HttpResponse
        @param headers: the headers dictionary
        '''
        for key, val in headers.items:
            setattr(response, key, val)
    
    def response(self, qs, headers = {}, fields = []):
        '''
        Returns a response according to the type of request made. This is done by passing in the 
        Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
        to json. This is a utility for serializing objects.
        
        If the query param single=true is found, then will return a single object if the queryset returns only
        one object. Otherwise all queries are sent in a list by default. This option is only available for json.
        
        @param request: the request object
        @param qs: an iterable of manager objects
        @param headers: a dictionary of headers to add
        @param fields: a list of fields to include
        @return the HttpResponse object
        '''
        is_single = len(qs) == 1
        if 'xml' in self.accept:
            if not fields:
                data = sz.serialize("xml", qs)
            else:
                data = sz.serialize("xml", qs, fields = fields)
            ct = "application/xml"
        else: #defaults to json if nothing else is found of appropriate use
            if not fields:
                data = sz.serialize("json", qs)
            else:
                data = sz.serialize("json", qs, fields = fields)
            data = data[1:-1] if is_single and self.params.get("single", "false").lower() == "true" else data
            ct = "application/json"
        resp = HttpResponse(data, content_type = ct)
        if headers:
            self.set_headers(resp, headers)
        return resp
    
    def other_response(self, data = None, headers = {}):
        '''
        Returns a response according to the type of request made. This is done by passing in the 
        Accept header with the desired Content-Type. If a recognizable content type is not found, defaults
        to json. Data should already be formatted in the correct Content-Type. This is a utility for sending all other responses.
        
        @param request: the request object
        @param data: the data to send; if None will send nothing with status 204
        @return the HttpResponse object
        '''
        if data is not None:
            if 'xml' in self.accept:
                ct = "application/xml"
            else: #defaults to json if nothing else is found of appropriate use
                ct = "application/json"
            status = 200
        else:
            data = ""
            ct = None
            status = 204
        resp = HttpResponse(data, content_type = ct, status = status)
        if headers:
            self.set_headers(resp, headers)
        return resp
    
    class Meta:
        abstract = True