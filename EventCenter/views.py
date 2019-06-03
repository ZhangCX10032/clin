import json
import rsa
import base64

from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, DataError
from django.views.decorators.csrf import csrf_exempt

from .forms import LoginForm
from .responses import success_json_response, error_json_response
from .serializers import event_list_serializer, event_serializer, comment_list_serializer, event_deserializer, \
    comment_deserializer, comment_serializer, event_updater, like_list_serializer, like_deserializer, like_serializer, \
    channel_list_serializer, channel_updater, channel_serializer
from .models import Event, Channel, Comment, Like


@csrf_exempt
def login(request):
    if request.user.is_authenticated:
        print('login access')
        return success_json_response({'user': {'username': request.user.username,
                                               'isAdmin': request.user.is_staff or request.user.is_superuser}})

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            private_key = rsa.PrivateKey.load_pkcs1(('-----BEGIN RSA PRIVATE KEY-----\n \
                MIICXAIBAAKBgQClKNC9Gyk0K2d3x1XnJhsNQOm4pqem0UmElIH6rvUSHmbx9R1S\n \
                HZSLqE7biTcYhkU8gYe0+fIBeExt/qW4L6IbEB3XG/Xv0rarK18vCNulkD43eDae\n \
                JZPOIdy3nItXiBIpNQxEu8MiOtqTIPeGIcueIOP0C3+HeIZFiKPSZMoteQIDAQAB\n \
                AoGBAIQQyCF/N4p87qar4bgNE3Kcpoe906+kCOqYKft/rX4Ii38M5p5EAwVN14jb\n \
                BxB4RaLlXNPNTcP5IvyNtIw8op1CZJZxdneTKjquH+cBYdZE5v/UpQfa1PP3o22b\n \
                0/jGtHyCGJzzZ/+DlCtgTBLJsK7e5mJPw8X9hvqR+kIPDoXRAkEA01CL26Ufr0PC\n \
                /gGMpOvI6iK8DDwBdE8ISrW+XkgixSnPBZcYrhKnLi3zvOg5yEMEBCqt9Wi/qorW\n \
                h4ZBqzVbVQJBAMgVq936/15lwJeSv6Z7Ssm7iVsLETr7xFt9m8CT3+FykrtNBZQx\n \
                rOm/daLfyTjXNsv0EaePVF6xCfyuQ7698ZUCQBeqsb9L4xySDki8i6/86GewtDb6\n \
                kX8hSuBzMnsEwUAryo/puE3msOqvItlJeQ9A0jZVQV52+OB05EoRc1FljHECQCDT\n \
                bV79zuetyesUKF0n3R07p01Ig4spww0/jk4J9LEIGwqfmEq326Z9ws716A1rQZI0\n \
                eLEE0tK2OO07qeGhSAECQEXbD/vOhPYzpME56uyev9hNBm61k4Uc4JDpq6yz81OB\n \
                +NMBbLi1tT4RBVxJKPD38CFKR0umqzVRygAl8PuOECY=\n \
                -----END RSA PRIVATE KEY-----'))

            password = rsa.decrypt(base64.b64decode(password.encode('utf-8')), private_key)

            user = auth.authenticate(username=username, password=password)

            if user is not None and user.is_active:
                auth.login(request, user)
                return success_json_response({'user': {'username': request.user.username,
                                                       'isAdmin': request.user.is_staff or request.user.is_superuser}})
            else:
                return error_json_response('Wrong password. Please try again.')
        else:
            return error_json_response('Invalid username')

    return error_json_response('User not logged in.')


@csrf_exempt
def logout(request):
    auth.logout(request)
    return success_json_response({'message': 'Successfully log out'})


@csrf_exempt
def reject(request):
    return error_json_response('User not logged in.')


@login_required
@csrf_exempt
def event_list(request):
    if request.method == 'GET':
        events = Event.objects.all()
        args = request.GET

        try:
            channel_id = args.get('channel_id')
            if channel_id:
                events = events.filter(channel_id=int(channel_id))

            since = args.get('since')
            if since:
                events = events.filter(timestamp__gte=int(since))

            until = args.get('until')
            if until:
                events = events.filter(timestamp__lte=int(until))

            count = events.count()
            offset = int(args.get('offset', 0))
            limit = int(args.get('limit', 50))
            events = events.order_by('-id')[offset:offset + limit]
        except ValueError:
            return error_json_response('Invalid arguments')

        return success_json_response({'events': event_list_serializer(events), 'count': count})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            if data['title'] == '':
                return error_json_response('Empty event title')
            if data['description'] == '':
                return error_json_response('Empty event description')
            if data['location'] == '':
                return error_json_response('Empty event location')
            if data['image_url'] == '':
                return error_json_response('Empty event image url')
            if not str(data['timestamp']).isdigit():
                return error_json_response('Invalid / Empty event timestamp')
            if not str(data['channel_id']).isdigit():
                return error_json_response('Invalid / Empty event channel id')

            event = event_deserializer(data)
            event.save()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except Channel.DoesNotExist:
            return error_json_response('No such channel')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'event': event_serializer(event)})


@login_required
@csrf_exempt
def event_detail(request, pk):
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return error_json_response('No such event')

    if request.method == 'GET':
        return success_json_response({'event': event_serializer(event)})

    elif request.method == 'PUT':
        if not is_admin(request):
            return error_json_response('Authority required')

        try:
            data = json.loads(request.body)

            if data['title'] == '':
                return error_json_response('Empty event title')
            if data['description'] == '':
                return error_json_response('Empty event description')
            if data['location'] == '':
                return error_json_response('Empty event location')
            if data['image_url'] == '':
                return error_json_response('Empty event image url')
            if not str(data['timestamp']).isdigit():
                return error_json_response('Invalid / Empty event timestamp')
            if not str(data['channel_id']).isdigit():
                return error_json_response('Invalid / Empty event channel id')

            event = event_updater(event, data)
            event.save()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except Channel.DoesNotExist:
            return error_json_response('No such channel')
        except DataError:
            return error_json_response('Invalid date')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'event': event_serializer(event)})

    elif request.method == 'DELETE':
        if not is_admin(request):
            return error_json_response('Authority required')

        event.delete()
        return success_json_response({'message': 'Event successfully deleted'})


@login_required
@csrf_exempt
def comment_list(request, event_id):
    if request.method == 'GET':
        comments = Comment.objects.filter(event_id=event_id)
        count = comments.count()
        args = request.GET

        try:
            offset = int(args.get('offset', 0))
            limit = int(args.get('limit', 50))
        except ValueError:
            return error_json_response('Invalid arguments')

        comments = comments.order_by('-id')[offset:offset + limit]
        return success_json_response({'comments': comment_list_serializer(comments), 'count': count})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            data['event_id'] = event_id
            data['user_id'] = request.user.id

            if data['title'] == '':
                return error_json_response('Empty comment title')
            if data['content'] == '':
                return error_json_response('Empty comment content')

            comment = comment_deserializer(data)
            comment.save()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except Event.DoesNotExist:
            return error_json_response('No such event')
        except User.DoesNotExist:
            return error_json_response('No such user')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'comment': comment_serializer(comment)})

    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            comment_id = data['comment_id']
            comment = Comment.objects.get(pk=comment_id)
            comment.delete()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except Comment.DoesNotExist:
            return error_json_response('No such comment')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'message': 'Comment successfully deleted'})


@login_required
@csrf_exempt
def like_list(request, event_id):
    if request.method == 'GET':
        likes = Like.objects.filter(event_id=event_id)
        count = likes.count()
        args = request.GET

        try:
            offset = int(args.get('offset', 0))
            limit = int(args.get('limit', 50))
        except ValueError:
            return error_json_response('Invalid arguments')

        likes = likes.order_by('-id')[offset:offset + limit]
        return success_json_response({'likes': like_list_serializer(likes), 'count': count})

    elif request.method == 'POST':
        try:
            data = {'event_id': event_id, 'user_id': request.user.id}
            like = like_deserializer(data)
            if not Like.objects.filter(event_id=event_id, user_id=like.user_id).exists():
                like.save()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except Event.DoesNotExist:
            return error_json_response('No such event')
        except User.DoesNotExist:
            return error_json_response('No such user')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'like': like_serializer(like)})

    elif request.method == 'DELETE':
        try:
            like = Like.objects.filter(event_id=event_id, user_id=request.user.id)
            if like.exists():
                like.delete()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except Event.DoesNotExist:
            return error_json_response('No such event')
        except User.DoesNotExist:
            return error_json_response('No such user')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'message': 'Successfully unliked'})


@login_required
@csrf_exempt
def channel_list(request):
    if request.method == 'GET':
        args = request.GET
        try:
            offset = int(args.get('offset', 0))
            limit = int(args.get('limit', 10))
        except ValueError:
            return error_json_response('Invalid arguments')

        count = Channel.objects.all().count()
        channels = Channel.objects.all().order_by('-id')[offset:offset + limit]
        return success_json_response({'channels': channel_list_serializer(channels),
                                      'count': count})

    elif request.method == 'POST':
        if not is_admin(request):
            return error_json_response('Authority required')
        try:
            data = json.loads(request.body)
            if data['name'] == '':
                return error_json_response('Empty channel name')

            channel = Channel(**data)
            channel.save()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except IntegrityError:
            return error_json_response('Duplicated channel name')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'channel': channel_serializer(channel)})

    elif request.method == 'PUT':
        if not is_admin(request):
            return error_json_response('Authority required')
        try:
            data = json.loads(request.body)
            channel = Channel.objects.get(pk=data['id'])

            if data['name'] == '':
                return error_json_response('Empty channel name')

            channel = channel_updater(channel, data)
            channel.save()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except IntegrityError:
            return error_json_response('Duplicated channel name')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'channel': channel_serializer(channel)})

    elif request.method == 'DELETE':
        if not is_admin(request):
            return error_json_response('Authority required')
        try:
            data = json.loads(request.body)
            channel = Channel.objects.get(pk=data['id'])
            channel.delete()
        except ValueError:
            return error_json_response('Invalid JSON file')
        except (KeyError, TypeError):
            return error_json_response('Invalid arguments')

        return success_json_response({'message': 'Channel Successfully deleted'})


def is_admin(request):
    return request.user.is_superuser or request.user.is_staff
