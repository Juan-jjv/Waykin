/** Profile pictures for the demo family, keyed by display name. Size and position frame each face in a circle. */
export interface Avatar {
  src: string;
  size: string;
  position: string;
}

const AVATARS: Record<string, Avatar> = {
  sam: { src: "/avatars/sam.jpg", size: "143%", position: "40% 20%" },
  priya: { src: "/avatars/priya.jpg", size: "195%", position: "46% 23%" },
  maya: { src: "/avatars/maya.jpg", size: "180%", position: "48% 14%" },
};

export function avatarFor(name: string): Avatar | null {
  return AVATARS[name.trim().toLowerCase()] ?? null;
}
