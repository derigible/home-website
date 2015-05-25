'''
Created on May 17, 2015

@author: derigible
'''
from django.views.generic.base import View
from controllers.utils import response as resp, err, other_response as oresp
from controllers.utils import authenticated, read, has_level
from db.models import Post as BlogPost, Entry, Comment as comment
from db.models import Poster as User
from json import loads as load
from django.utils.decorators import method_decorator


class Entry(View):
    '''
    The view for entity-type views. Extend from this class and then set register_route to true.
    You also need to set the model variable to the model you are going to be using in the view.
    '''
    register_route = False
    model = Entry
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all entities. Otherwise, the args can come in two formats:
        
            1) the first arg in the path (passed in as a path variable) is an id of the entity
                a) filter args need to be passed in as query params
            2) add as many ids as you can in the path in this manner: /1/2/3/4/.../ 
                
        Note that the query params need to match the name of the model fields in order to work.
        '''
        if args[0] is None:
            return resp(request, self.model.objects.filter(**request.GET))
        elif len(args) == 1:
            return resp(request, self.model.objects.filter(id = args[0]))
        else:
            return resp(request, self.model.objects.filter(id__in = args))
    
    def post(self, request, *args, **kwargs):
        '''
        The post currently only accepts json.
        '''
        j = load(read(request))
        bp = self.model.objects.create(user = request.user, **j["data"])
        bp.labels.add(*j["labels"])
        return resp(request, (bp,))
    
    def put(self, request, *args, **kwargs):
        '''
        The put currently only accepts json.
        '''
        j = load(read(request))
        bp = self.model.objects.update(user = request.user, **j["data"])
        bp.labels.add(*j["add_labels"])
        bp.labels.remove(*j["delete_labels"])
        return resp(request, (bp,))
    
    def delete(self, request, *args, **kwargs):
        '''
        Delete an entity. This is a no payload endpoint where you can delete either in bulk by adding
        doing one of the three things:
        
            1) a single entity: .../entity/<id>/ where you just add one id in the path
            2) multiple entities: .../entity/<id>/<id2>/.../ where you add as many ids as you want in the path
            3) leave the args blank and add query param with at least one query param called ids as follows:
                
                    ids=1,2,3,4,5
                    
                note that the ids are a csv.
                
            Note that the args argument can also be used to help narrow down from the list of ids those that
            contain other query attributes. Note that this query attributes need to have the names of the model
            fields, just like in getting objects.
        '''
        if args[0] is None:
            if "ids" not in request.GET:
                return err("Did not contain any valid ids to delete.")
            ids = request.GET.get("ids").split(',')
            deletes = self.model.objects.filter(id__in = ids, **request.GET)
        elif len(args) == 1:
            deletes = self.model.objects.get(id = args[0])
        else:
            deletes = self.model.objects.filter(id__in = args)
        
        deletes.delete()
        
        return oresp(request)

class Post(Entry):
    '''
        @POST
        Creates a new post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "data" {
                    "title" : "<title text>",
                    "text" : "<text>"
                }
                "labels : [
                    "<label name>",...
                ]
            }
        
        @PUT
        Updates a post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "post" {
                    "title" : "<title text>",
                    "text" : "<text>"
                }
                "add_labels : [
                    "<label name>",...
                ],
                "delete_labels : [
                    "<label name>",...
                ]
            }

    '''
    register_route = True
    model = BlogPost
    
    @method_decorator(authenticated)
    @method_decorator(has_level("creator"))
    def post(self, request, *args, **kwargs):
        return super(Post, self).post(request, *args, **kwargs)
    
    @method_decorator(authenticated)
    @method_decorator(has_level("creator"))
    def put(self, request, *args, **kwargs):
        return super(Post, self).put(request, *args, **kwargs)
    
    @method_decorator(authenticated)
    @method_decorator(has_level("master"))
    def delete(self, request, *args, **kwargs):
        return super(Post, self).delete(request, *args, **kwargs)
    
class Comment(Entry):
    '''
        @POST
        Creates a new comment for the post. The json should look like::
        
            {  
                "data" {
                    "title" : "<title text - Optional>",
                    "text" : "<text>",
                    "comment_id" : <commentId - Optional>,
                    "post_id" : <postId>
                }
                "labels : [
                    "<label name>",...
                ]
            }
        
        @PUT
        Updates a post for the blog. The blog post currently only accepts json, and
        the json should come in the following manner:
        
            {  
                "post" {
                    "title" : "<title text - Optional>",
                    "text" : "<text>"
                }
                "labels : [
                    "<label name>",...
                ],
                "delete_labels : [
                    "<label name>",...
                ]
            }

    '''
    register_route = True
    model = comment
    
    @method_decorator(authenticated)
    @method_decorator(has_level("commenter"))
    def post(self, request, *args, **kwargs):
        return super(Comment, self).post(request, *args, **kwargs)
    
    @method_decorator(authenticated)
    @method_decorator(has_level("commenter"))
    def put(self, request, *args, **kwargs):
        return super(Comment, self).put(request, *args, **kwargs)
        
    @method_decorator(authenticated)
    @method_decorator(has_level("creator"))
    def delete(self, request, *args, **kwargs):
        return super(Comment, self).delete(request, *args, **kwargs)
        
class Poster(View):
    '''
    The class that handles the poster objects.
    '''
    
    fields = ('email', 'joined_on', 'last_login', 'level')
    
    @method_decorator(authenticated)
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
    