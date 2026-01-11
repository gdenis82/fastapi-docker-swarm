import { AuthBarrier } from "@/components/auth-check";

export default function ProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthBarrier>{children}</AuthBarrier>;
}
