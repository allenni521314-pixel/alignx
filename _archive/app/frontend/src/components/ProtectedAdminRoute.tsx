import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Shield, User, LogIn } from 'lucide-react';

interface ProtectedAdminRouteProps {
  children: React.ReactNode;
}

const ProtectedAdminRoute: React.FC<ProtectedAdminRouteProps> = ({
  children,
}) => {
  const { user, loading, isAdmin, login } = useAuth();

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500 mx-auto mb-4"></div>
          <p className="text-gray-500">验证权限中...</p>
        </div>
      </div>
    );
  }

  // If the user is not logged in, redirect to landing
  if (!user) {
    return <Navigate to="/" replace />;
  }

  // If the user is not an admin, show an insufficient-permissions page
  if (!isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Card className="w-full max-w-md mx-4 bg-white border-gray-200">
          <CardHeader className="text-center">
            <div className="mx-auto w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
              <Shield className="h-8 w-8 text-red-600" />
            </div>
            <CardTitle className="text-xl text-gray-900">
              权限不足
            </CardTitle>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <div className="text-gray-500">
              <p className="mb-2">
                当前账户没有管理员权限。
              </p>
              <div className="bg-gray-50 rounded-lg p-3 mb-4">
                <div className="flex items-center justify-center space-x-2 text-sm">
                  <User className="h-4 w-4 text-gray-500" />
                  <span className="text-gray-600">
                    当前账户: {user.name || user.email}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  角色: {user.role === 'user' ? '普通用户' : user.role}
                </div>
              </div>
              <p className="text-sm">
                请使用管理员账户登录。
              </p>
            </div>

            <div className="space-y-3">
              <Button onClick={login} className="w-full bg-brand-600 hover:bg-brand-500 text-white">
                <LogIn className="h-4 w-4 mr-2" />
                切换账户
              </Button>

              <Button
                onClick={() => window.history.back()}
                className="w-full text-gray-500 hover:text-gray-900 hover:bg-gray-100"
                variant="ghost"
              >
                返回
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If the user is an admin, render the child components
  return <>{children}</>;
};

export default ProtectedAdminRoute;