from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status


class OCSViewSet(viewsets.ModelViewSet):

    def create(self, request, *args, **kwargs):
        """
        handles post request, suitable for single and multi creation

        Args:
            request ([dict]): can be dict or list of dicts

        Returns:
            [type]: [description]
        """
        # 'many' allows multi creation but any error
        # will fail the whole transaction
        try:
            serializer = self.get_serializer(
                data=request.data, many=isinstance(request.data, list))
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        except:
            # serializer.errors may return more details
            return Response({'failed': request.data}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': '200'}, status=status.HTTP_200_OK)

    def update_instance(self, elem, partial):
        instance = self.model.objects.get(id=elem['id'])
        serializer = self.get_serializer(instance, data=elem, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        handles incoming patch request, will redirect to put method

        Args:
            request ([type]): [description]

        Returns:
            [type]: [description]
        """
        kwargs['partial'] = True
        return self.put(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """
        handles put request, either as an update or partial update

        2 cases : 
            - request is a list : bulk update will be performed
            - request is a dict : single update

        Args:
            request ([type])

        Returns:
            [dict] :
                - success : all updates were successful
                - partial success : some updates have failed
                - failed : total failure
        """
        partial = kwargs.pop('partial', False)
        success = []
        failed = []
        if isinstance(request.data, list):
            for elem in request.data:
                try:
                    self.update_instance(elem, partial)
                    success += [elem]
                except:
                    failed += [elem]

            if not failed:
                return Response({'success': '200'}, status=status.HTTP_200_OK)
            elif failed and success:
                return Response({'partial success': failed}, status=status.HTTP_200_OK)
            else:
                return Response({'failed': failed}, status=status.HTTP_400_BAD_REQUEST)

        else:
            try:
                self.update_instance(request.data, partial)
            except:
                return Response({'failed': request.data}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': '200'}, status=status.HTTP_200_OK)
