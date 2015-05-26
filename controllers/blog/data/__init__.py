'''
Created on May 17, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import response as resp, err, other_response as oresp
from controllers.utils import read, has_level
from db.models import Post as BlogPost, Entry, Comment as comment, Label as label
from db.models import Poster as User
from json import loads as load
from django.utils.decorators import method_decorator


class Entity(View):
    '''
    The view for entity-type views. Extend from this class and then set register_route to true.
    You also need to set the model variable to the model you are going to be using in the view.
    
    This view will associate some user with every creation method. There may be a work around for this,
    such as making the user field as nullable.
    '''
    register_route = False
    model = Entry
    
    def __init__(self, **kwargs):
        '''
        Initialize the view with some of the data needed for the queries, such as the m2m field names.
        '''
        self.m2ms = self._get_m2ms()
        super(Entity, self).__init__(**kwargs)
    
    def _get_m2ms(self):
        '''
        Simple helper method to get the m2m field names of the model.
        '''
        return [str(m2m[0]).split('.')[-1] for m2m in self.model._meta.get_m2m_with_model()]
    
    def _get_qs(self, request, *args, **kwargs):
        '''
        A helper method to get the queryset, to be used for GET, PUT, and maybe DELETE. Look at the
        GET docs to see how this works.
        '''
        args = args[0].split('/')[:-1]
        if not args:
            qs = self.model.objects.all()
            if "ids" in request.GET:
                ids = request.GET.get('ids').split(',')
                qs = qs.filter(id__in = ids)
            reqDict = {field : request.GET[field] for field in self.model._meta.get_all_field_names() if field in request.GET}
            return qs.filter(**reqDict)      
        elif len(args) == 1:
            return self.model.objects.filter(id = args[0])
        else:
            reqDict = {field : request.GET[field] for field in self.model._meta.get_all_field_names() if field in request.GET}
            return self.model.objects.filter(id__in = args, **reqDict)
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all entities. Otherwise, the args can come in two formats:
        
            1) the first arg in the path (passed in as a path variable) is an id of the entity
                a) filter args need to be passed in as query params
            2) add as many ids as you can in the path in this manner: /1/2/3/4/.../ 
            3) add the query param ids as a csv for those entities by id you want: ids=1,2,3,4,...
                
        Note that the query params need to match the name of the model fields in order to work.
        '''
        return resp(request, self._get_qs(request, *args, **kwargs))
    
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
        j = load(read(request))
        bp = self.model.objects.create(user = request.user, **j["data"])
        if len(j) > 1: #there are many2many fields to add, lets add them
            for m2m in self.m2ms: #Get the name of the m2m used
                if m2m in j and type(j.get(m2m) == list):
                    bp.labels.add(*j[m2m])
        return resp(request, (bp,))
    
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
        j = load(read(request))
        qs = self._get_qs(request, *args, **kwargs)
        entity = qs.update(**j["data"])
        if len(j) > 1: #there are many2many fields to add and delete, lets add them
            for m2m in self.m2ms:
                if "add_" + m2m in j and type(j.get(m2m), list):
                    entity.labels.add(*j[m2m])
                if "delete_" + m2m in j and type(j.get(m2m), list):
                    entity.labels.remove(*j[m2m])
        return oresp(request)
    
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
            contain other query attributes. Note that these query attributes need to have the names of the model
            fields, just like in getting objects.
        '''
        args = args[0].split('/')[:-1]
        if not args:
            if "ids" not in request.GET:
                return err("Did not contain any valid ids to delete.")
            ids = request.GET.get("ids").split(',')
            reqDict = {field : request.GET[field] for field in self.model._meta.get_all_field_names() if field in request.GET}
            deletes = self.model.objects.filter(id__in = ids, **reqDict)
        elif len(args) == 1:
            deletes = self.model.objects.get(id = args[0])
        else:
            deletes = self.model.objects.filter(id__in = args)
        
        deletes.delete()
        
        return oresp(request)

class Post(Entity):
    '''
        @POST
        Creates a new post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "data" : {
                    "title" : "<title text>",
                    "text" : "<text>"
                },
                "labels" : [
                    "<label name>",...
                ]
            }
        
        @PUT
        Updates a post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "data" : {
                    "title" : "<title text>",
                    "text" : "<text>"
                },
                "add_labels" : [
                    "<label name>",...
                ],
                "delete_labels" : [
                    "<label name>",...
                ]
            }

    '''
    register_route = True
    model = BlogPost
    
    @method_decorator(has_level("creator"))
    def post(self, request, *args, **kwargs):
        return super(Post, self).post(request, *args, **kwargs)
    
    @method_decorator(has_level("creator"))
    def put(self, request, *args, **kwargs):
        return super(Post, self).put(request, *args, **kwargs)
    
    @method_decorator(has_level("master"))
    def delete(self, request, *args, **kwargs):
        return super(Post, self).delete(request, *args, **kwargs)
    
class Comment(Entity):
    '''
        @POST
        Creates a new comment for the post. The json should look like::
        
            {  
                "data" : {
                    "title" : "<title text - Optional>",
                    "text" : "<text>",
                    "comment_id" : <commentId - Optional>,
                    "post_id" : <postId>
                },
                "labels" : [
                    "<label name>",...
                ]
            }
        
        @PUT
        Updates a post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "data" : {
                    "title" : "<title text - Optional>",
                    "text" : "<text>"
                },
                "add_labels" : [
                    "<label name>",...
                ],
                "delete_labels" : [
                    "<label name>",...
                ]
            }

    '''
    register_route = True
    model = comment
    
    @method_decorator(has_level("commenter"))
    def post(self, request, *args, **kwargs):
        return super(Comment, self).post(request, *args, **kwargs)
    
    @method_decorator(has_level("commenter"))
    def put(self, request, *args, **kwargs):
        return super(Comment, self).put(request, *args, **kwargs)
        
    @method_decorator(has_level("creator"))
    def delete(self, request, *args, **kwargs):
        return super(Comment, self).delete(request, *args, **kwargs)
    
class Label(Entity):
    '''
    The class that handles labels. Json input looks like:
    
        {  
            "data" : {
                "name" : "<name>",
                "notes" : "<note - Optional>",
                "creator" : creator_id
            }
        }
    '''
    register_route = True
    model = label
    
    @method_decorator(has_level("moderator"))
    def post(self, request, *args, **kwargs):
        return super(Label, self).post(request, *args, **kwargs)
    
    @method_decorator(has_level("moderator"))
    def put(self, request, *args, **kwargs):
        
        return super(Label, self).put(request, *args, **kwargs)
    
    @method_decorator(has_level("master"))
    def delete(self, request, *args, **kwargs):
        return super(Label, self).delete(request, *args, **kwargs)
        
class Poster(View):
    '''
    The class that handles the poster objects.
    '''
    
    fields = ('email', 'joined_on', 'last_login', 'level')
    
    @method_decorator(has_level("creator"))
    def get(self, request, *args, **kwargs):
        '''
        Get all the posters in the system. The first arg should be the email or the primary key of the 
        user to use
        '''
        if args[0] is not None:
            if args[0].isdigit():
                return resp(request, User.objects.filter(id = args[0]), fields = self.fields)
            else:
                return resp(request, User.objects.filter(email = args[0]), fields = self.fields)
        elif request.user.level >= 4:
            return resp(request, User.objects.all(), fields = self.fields)
        else:
            return err("Your level of {} is not allowed to see all users.".format(User.get_level_name(request.user.level)), 403)
    