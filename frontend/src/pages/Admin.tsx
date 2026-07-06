import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { api, apiErrorMessage } from "../api/client";
import type { Permission, Profile, User } from "../api/types";

export default function Admin() {
  const [tab, setTab] = useState<"users" | "profiles" | "squad">("users");
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Administración</h1>
      <div className="flex flex-wrap gap-2">
        <button className={tab === "users" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("users")}>
          Usuarios
        </button>
        <button className={tab === "profiles" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("profiles")}>
          Perfiles y permisos
        </button>
        <button className={tab === "squad" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("squad")}>
          Convocados
        </button>
      </div>
      {tab === "users" && <UsersPanel />}
      {tab === "profiles" && <ProfilesPanel />}
      {tab === "squad" && <SquadPanel />}
    </div>
  );
}

function UsersPanel() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: async () => (await api.get<User[]>("/admin/users")).data });
  const profiles = useQuery({ queryKey: ["admin-profiles"], queryFn: async () => (await api.get<Profile[]>("/admin/profiles")).data });

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [profile, setProfile] = useState("");
  const [error, setError] = useState("");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin-users"] });
    qc.invalidateQueries({ queryKey: ["admin-profiles"] });
  };

  const create = useMutation({
    mutationFn: async () => (await api.post("/admin/users", { username, password, email, profile })).data,
    onSuccess: () => {
      setUsername(""); setPassword(""); setEmail(""); setError("");
      invalidate();
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const toggle = useMutation({
    mutationFn: async (u: User) => (await api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active })).data,
    onSuccess: invalidate,
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/admin/users/${id}`)).data,
    onSuccess: invalidate,
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    create.mutate();
  }

  const profileList = profiles.data ?? [];

  return (
    <div className="space-y-5 lg:grid lg:grid-cols-3 lg:gap-5 lg:space-y-0">
      <form onSubmit={onCreate} className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-slate-300">Nuevo cliente</h2>
        <input className="input" placeholder="usuario" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <input className="input" type="password" placeholder="contraseña" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <input className="input" placeholder="email (opcional)" value={email} onChange={(e) => setEmail(e.target.value)} />
        <select className="input" value={profile} onChange={(e) => setProfile(e.target.value)} required>
          <option value="" disabled>Perfil…</option>
          {profileList.map((p) => (
            <option key={p.id} value={p.name}>
              {p.name} {p.max_users != null ? `(${p.user_count}/${p.max_users})` : ""}
            </option>
          ))}
        </select>
        {error && <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{error}</div>}
        <button className="btn-primary w-full" disabled={create.isPending}>
          {create.isPending ? "Creando…" : "Crear usuario"}
        </button>
      </form>

      <div className="card overflow-x-auto lg:col-span-2">
        <table className="w-full min-w-[360px]">
          <thead className="border-b border-line bg-panel2/50">
            <tr>
              <th className="th">Usuario</th>
              <th className="th hidden sm:table-cell">Perfil</th>
              <th className="th hidden sm:table-cell">Estado</th>
              <th className="th text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {(users.data ?? []).map((u) => (
              <tr key={u.id} className="border-b border-line/50">
                <td className="td">
                  <div className="font-medium">{u.username}</div>
                  {/* perfil+estado visible en móvil bajo el nombre */}
                  <div className="flex gap-1.5 sm:hidden mt-0.5">
                    <span className="chip text-[10px]">{u.profile}</span>
                    <span className={`text-xs ${u.is_active ? "text-pitch" : "text-slate-500"}`}>
                      {u.is_active ? "activo" : "inactivo"}
                    </span>
                  </div>
                </td>
                <td className="td hidden sm:table-cell">
                  <span className="chip">{u.profile}</span>
                </td>
                <td className="td hidden sm:table-cell">
                  <span className={u.is_active ? "text-pitch" : "text-slate-500"}>
                    {u.is_active ? "activo" : "inactivo"}
                  </span>
                </td>
                <td className="td text-right">
                  <button className="btn-ghost px-2 py-1 text-xs" onClick={() => toggle.mutate(u)}>
                    {u.is_active ? "Desactivar" : "Activar"}
                  </button>
                  <button className="btn-ghost ml-1 px-2 py-1 text-xs text-rose-300" onClick={() => remove.mutate(u.id)}>
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProfilesPanel() {
  const qc = useQueryClient();
  const profiles = useQuery({ queryKey: ["admin-profiles"], queryFn: async () => (await api.get<Profile[]>("/admin/profiles")).data });
  const perms = useQuery({ queryKey: ["admin-perms"], queryFn: async () => (await api.get<Permission[]>("/admin/permissions")).data });

  const [name, setName] = useState("");
  const [maxUsers, setMaxUsers] = useState("");
  const [error, setError] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-profiles"] });

  const create = useMutation({
    mutationFn: async () =>
      (await api.post("/admin/profiles", {
        name,
        description: "",
        max_users: maxUsers ? Number(maxUsers) : null,
        permissions: ["view_dashboard"],
      })).data,
    onSuccess: () => {
      setName(""); setMaxUsers(""); setError("");
      invalidate();
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  return (
    <div className="space-y-5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setError("");
          create.mutate();
        }}
        className="card flex flex-wrap items-end gap-3 p-4"
      >
        <div>
          <label className="mb-1 block text-xs text-slate-400">Nuevo perfil</label>
          <input className="input w-48" placeholder="nombre" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Cupo (vacío = ilimitado)</label>
          <input className="input w-40" placeholder="máx. usuarios" inputMode="numeric" value={maxUsers} onChange={(e) => setMaxUsers(e.target.value)} />
        </div>
        <button className="btn-primary" disabled={create.isPending}>
          Crear perfil
        </button>
        {error && <span className="text-xs text-rose-300">{error}</span>}
      </form>

      <div className="grid gap-4 md:grid-cols-2">
        {(profiles.data ?? []).map((p) => (
          <ProfileCard key={p.id} profile={p} permissions={perms.data ?? []} onChanged={invalidate} />
        ))}
      </div>
    </div>
  );
}

function ProfileCard({
  profile,
  permissions,
  onChanged,
}: {
  profile: Profile;
  permissions: Permission[];
  onChanged: () => void;
}) {
  const [selected, setSelected] = useState<string[]>(profile.permissions);
  const [maxUsers, setMaxUsers] = useState(profile.max_users?.toString() ?? "");
  const [error, setError] = useState("");
  const dirty =
    JSON.stringify([...selected].sort()) !== JSON.stringify([...profile.permissions].sort()) ||
    (profile.max_users?.toString() ?? "") !== maxUsers;

  const save = useMutation({
    mutationFn: async () =>
      (await api.patch(`/admin/profiles/${profile.id}`, {
        permissions: profile.is_system ? undefined : selected,
        max_users: maxUsers ? Number(maxUsers) : null,
      })).data,
    onSuccess: () => {
      setError("");
      onChanged();
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function toggle(key: string) {
    if (profile.is_system) return;
    setSelected((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));
  }

  return (
    <div className="card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{profile.name}</span>
          {profile.is_system && <span className="chip">sistema</span>}
        </div>
        <span className="text-xs text-slate-400">
          {profile.user_count}
          {profile.max_users != null ? ` / ${profile.max_users}` : ""} usuarios
        </span>
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {permissions.map((perm) => {
          const on = selected.includes(perm.key);
          return (
            <button
              key={perm.key}
              title={perm.description}
              onClick={() => toggle(perm.key)}
              disabled={profile.is_system}
              className={`rounded-full border px-2 py-0.5 text-xs transition ${
                on ? "border-pitch bg-pitch/20 text-pitch" : "border-line bg-panel2 text-slate-400"
              } ${profile.is_system ? "cursor-not-allowed opacity-70" : "hover:border-pitch/60"}`}
            >
              {perm.key}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        <label className="text-xs text-slate-400">Cupo</label>
        <input
          className="input w-24"
          placeholder="∞"
          inputMode="numeric"
          value={maxUsers}
          onChange={(e) => setMaxUsers(e.target.value)}
        />
        <button
          className="btn-primary ml-auto px-3 py-1.5 text-xs"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "…" : "Guardar"}
        </button>
      </div>
      {error && <div className="mt-2 text-xs text-rose-300">{error}</div>}
    </div>
  );
}

// ── Convocados ────────────────────────────────────────────────────────────────

interface PlayerRow {
  id: number;
  name: string;
  team_id: number;
  team: string;
  position: string;
  sot_per_90: number;
  source: string;
}

function SquadPanel() {
  const qc = useQueryClient();
  const [teamFilter, setTeamFilter] = useState<string>("");

  const { data: allPlayers, isLoading } = useQuery({
    queryKey: ["admin-players"],
    queryFn: async () => (await api.get<PlayerRow[]>("/admin/players")).data,
  });

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/admin/players/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-players"] }),
  });

  if (isLoading) return <p className="text-slate-400">Cargando jugadores…</p>;
  if (!allPlayers?.length) return (
    <div className="card p-6 text-center text-slate-500">
      No hay jugadores en la base de datos.
    </div>
  );

  const teams = Array.from(new Map(allPlayers.map((p) => [p.team_id, p.team])).entries())
    .sort((a, b) => a[1].localeCompare(b[1]));

  const filtered = teamFilter
    ? allPlayers.filter((p) => String(p.team_id) === teamFilter)
    : allPlayers;

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Elimina jugadores que no están en la convocatoria oficial. Los que queden en la lista aparecen en el Bet Builder.
      </p>

      <select
        className="input w-full sm:w-64"
        value={teamFilter}
        onChange={(e) => setTeamFilter(e.target.value)}
      >
        <option value="">— Todos los equipos ({allPlayers.length}) —</option>
        {teams.map(([id, name]) => {
          const count = allPlayers.filter((p) => p.team_id === id).length;
          return <option key={id} value={String(id)}>{name} ({count})</option>;
        })}
      </select>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[440px] text-sm">
          <thead className="border-b border-line bg-panel2/50">
            <tr>
              <th className="th text-left">Jugador</th>
              <th className="th text-left hidden sm:table-cell">Equipo</th>
              <th className="th text-center">Pos.</th>
              <th className="th text-center">SOT/90</th>
              <th className="th text-center">Fuente</th>
              <th className="th text-center w-20">Quitar</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/40">
            {filtered.map((p) => (
              <tr key={p.id}>
                <td className="td font-medium">{p.name}</td>
                <td className="td hidden sm:table-cell text-slate-400 text-xs">{p.team}</td>
                <td className="td text-center"><span className="chip text-[10px]">{p.position}</span></td>
                <td className="td text-center tabular-nums text-xs">{p.sot_per_90}</td>
                <td className="td text-center text-[10px] text-slate-500">{p.source}</td>
                <td className="td text-center">
                  <button
                    onClick={() => remove.mutate(p.id)}
                    disabled={remove.isPending}
                    className="rounded px-2 py-0.5 text-xs text-rose-400 hover:bg-rose-900/30 transition-colors"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
