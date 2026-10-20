def user_roles(request):
    # Mesma regra do GroupRequiredMixin com group_required = ['Manager']:
    # superusuário ou membro do grupo Manager.
    user = request.user
    is_manager = user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='Manager').exists()
    )
    return {'is_manager': is_manager}
