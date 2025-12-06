from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, Http404
from django.db import transaction
from .models import Tenant, TenantStatusHistory


def is_superuser(user):
    """Check if user is superuser."""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def tenant_suspend(request, tenant_id):
    """
    Suspend a tenant temporarily.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        tenant.suspend(reason=reason, changed_by=request.user)
        messages.success(
            request, 
            f'Tenant "{tenant.name}" has been suspended.'
        )
        return redirect('tenant-detail', pk=tenant.id)
    
    return render(request, 'tenants/tenant_suspend.html', {
        'tenant': tenant
    })


@login_required
@user_passes_test(is_superuser)
def tenant_unsuspend(request, tenant_id):
    """
    Unsuspend a tenant.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if request.method == 'POST':
        tenant.unsuspend(changed_by=request.user)
        messages.success(
            request, 
            f'Tenant "{tenant.name}" has been unsuspended.'
        )
        return redirect('tenant-detail', pk=tenant.id)
    
    return render(request, 'tenants/tenant_unsuspend.html', {
        'tenant': tenant
    })


@login_required
@user_passes_test(is_superuser)
def tenant_soft_delete(request, tenant_id):
    """
    Soft delete a tenant.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        tenant.soft_delete(reason=reason, changed_by=request.user)
        messages.success(
            request, 
            f'Tenant "{tenant.name}" has been deleted.'
        )
        return redirect('tenant-list')
    
    return render(request, 'tenants/tenant_soft_delete.html', {
        'tenant': tenant
    })


@login_required
@user_passes_test(is_superuser)
def tenant_restore(request, tenant_id):
    """
    Restore a soft-deleted tenant.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if not tenant.is_deleted:
        messages.error(request, 'This tenant is not deleted.')
        return redirect('tenant-detail', pk=tenant.id)
    
    if request.method == 'POST':
        tenant.restore(changed_by=request.user)
        messages.success(
            request, 
            f'Tenant "{tenant.name}" has been restored.'
        )
        return redirect('tenant-detail', pk=tenant.id)
    
    return render(request, 'tenants/tenant_restore.html', {
        'tenant': tenant
    })


@login_required
@user_passes_test(is_superuser)
def tenant_expire_trial(request, tenant_id):
    """
    Mark a tenant's trial as expired.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if request.method == 'POST':
        tenant.expire_trial(changed_by=request.user)
        messages.success(
            request, 
            f'Trial for tenant "{tenant.name}" has been expired.'
        )
        return redirect('tenant-detail', pk=tenant.id)
    
    return render(request, 'tenants/tenant_expire_trial.html', {
        'tenant': tenant
    })


@login_required
@user_passes_test(is_superuser)
def tenant_permanent_delete(request, tenant_id):
    """
    Permanently delete a tenant with confirmation.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if not tenant.is_deleted:
        messages.error(request, 'Only deleted tenants can be permanently deleted.')
        return redirect('tenant-detail', pk=tenant.id)
    
    if request.method == 'POST':
        # Get confirmation text
        confirmation = request.POST.get('confirmation', '')
        if confirmation != f"DELETE {tenant.name.upper()}":
            messages.error(request, 'Incorrect confirmation text.')
            return render(request, 'tenants/tenant_permanent_delete.html', {
                'tenant': tenant,
                'error': 'Please type the confirmation text exactly as shown.'
            })
        
        try:
            with transaction.atomic():
                # In a real implementation, you might want to cascade delete related data
                # or archive it before permanent deletion
                tenant.permanent_delete()
                messages.success(
                    request, 
                    f'Tenant "{tenant.name}" has been permanently deleted.'
                )
                return redirect('tenant-list')
        except Exception as e:
            messages.error(request, f'Error deleting tenant: {str(e)}')
            return render(request, 'tenants/tenant_permanent_delete.html', {
                'tenant': tenant,
                'error': str(e)
            })
    
    return render(request, 'tenants/tenant_permanent_delete.html', {
        'tenant': tenant
    })


@login_required
@user_passes_test(is_superuser)
def bulk_tenant_actions(request):
    """
    Bulk actions on multiple tenants.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    action = request.POST.get('action')
    tenant_ids = request.POST.getlist('tenant_ids', [])
    
    if not tenant_ids:
        return JsonResponse({'error': 'No tenants selected'}, status=400)
    
    if action not in ['suspend', 'unsuspend', 'soft_delete', 'restore', 'expire_trial']:
        return JsonResponse({'error': 'Invalid action'}, status=400)
    
    try:
        tenants = Tenant.objects.filter(id__in=tenant_ids)
        count = 0
        
        if action == 'suspend':
            reason = request.POST.get('reason', 'Bulk suspension')
            for tenant in tenants:
                if tenant.status == 'active':
                    tenant.suspend(reason=reason, changed_by=request.user)
                    count += 1
            message = f'{count} tenants have been suspended.'
            
        elif action == 'unsuspend':
            for tenant in tenants:
                if tenant.status == 'suspended':
                    tenant.unsuspend(changed_by=request.user)
                    count += 1
            message = f'{count} tenants have been unsuspended.'
            
        elif action == 'soft_delete':
            reason = request.POST.get('reason', 'Bulk deletion')
            for tenant in tenants:
                if not tenant.is_deleted:
                    tenant.soft_delete(reason=reason, changed_by=request.user)
                    count += 1
            message = f'{count} tenants have been deleted.'
            
        elif action == 'restore':
            for tenant in tenants:
                if tenant.is_deleted:
                    tenant.restore(changed_by=request.user)
                    count += 1
            message = f'{count} tenants have been restored.'
            
        elif action == 'expire_trial':
            for tenant in tenants:
                if tenant.status == 'active':
                    tenant.expire_trial(changed_by=request.user)
                    count += 1
            message = f'{count} tenants trials have been expired.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


class TenantStatusHistoryView(LoginRequiredMixin, ListView):
    """
    View to show status history for a tenant.
    """
    model = TenantStatusHistory
    template_name = 'tenants/tenant_status_history.html'
    context_object_name = 'history'
    paginate_by = 20
    
    def get_queryset(self):
        tenant_id = self.kwargs.get('tenant_id')
        return TenantStatusHistory.objects.filter(
            tenant_id=tenant_id
        ).order_by('-changed_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_id = self.kwargs.get('tenant_id')
        context['tenant'] = get_object_or_404(Tenant, id=tenant_id)
        return context