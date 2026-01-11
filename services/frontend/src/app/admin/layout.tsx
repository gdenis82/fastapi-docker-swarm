import { AuthBarrier } from "@/components/auth-check";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthBarrier>{children}</AuthBarrier>;
}
