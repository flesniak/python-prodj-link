from construct import Bytes, Const, Default, Enum, FocusedSeq, GreedyBytes, If, Int32ub, Pass, PascalString, Prefixed, Struct, Switch, this

RpcMsgType = Enum(Int32ub,
  call = 0,
  reply = 1
)

RpcReplyStat = Enum(Int32ub,
  accepted = 0,
  denied = 1
)

RpcAcceptStat = Enum(Int32ub,
  success = 0,
  prog_unavail = 1,
  prog_mismatch = 2,
  prog_unsupp = 3,
  garbage_args = 4
)

RpcRejectStat = Enum(Int32ub,
  rpc_mismatch = 0,
  auth_error = 1
)

RpcAuthStat = Enum(Int32ub,
  badcred = 0,
  rejectedcred = 1,
  badverf = 2,
  rejectedverf = 3,
  tooweak = 4
)

RpcAuthFlavor = Enum(Int32ub,
  null = 0,
  unix = 1,
  short = 2,
  des = 3
)

RpcAuthUnix = Struct(
  "stamp" / Int32ub,
  "machine_name" / Default(PascalString(Int32ub, encoding="ascii"), ""),
  "uid" / Default(Int32ub, 0),
  "gid" / Default(Int32ub, 0),
  "gids" / Default(Int32ub, 0) # should be length-prefixed array?
)

RpcAuthShort = Pass
RpcAuthDes = Pass

RpcOpaqueAuth = Struct(
  "flavor" / Default(RpcAuthFlavor, "null"),
  "content" / Prefixed(Int32ub, Switch(this.flavor, {
    "null": Pass,
    "unix": RpcAuthUnix,
    "short": RpcAuthShort,
    "des": RpcAuthDes
  }))
)

PortmapPort = 111
PortmapVersion = 2
PortmapProcedure = Enum(Int32ub,
  null = 0,
  set = 1,
  unset = 2,
  getport = 3,
  dump = 4,
  call_result = 5
)

PortmapProtocol = Enum(Int32ub,
  ip = 6,
  udp = 17
)

RpcProgram = Enum(Int32ub,
  portmap = 100000,
  nfs = 100003,
  mount = 100005
)

PortmapArgs = Struct(
  "prog" / RpcProgram,
  "vers" / Int32ub,
  "prot" / PortmapProtocol,
  "port" / Default(Int32ub, 0)
)

PortmapRes = Int32ub

NfsVersion = 2
NfsProcedure = Enum(Int32ub,
  null = 0,
  getattr = 1,
  sattrargs = 2,
  root = 3,
  lookup = 4,
  readlink = 5,
  read = 6,
  writecache = 7,
  write = 8,
  create = 9,
  remove = 10,
  rename = 11,
  link = 12,
  symlink = 13,
  mkdir = 14,
  rmdir = 15,
  readdir = 16,
  statfs = 17
)

MountVersion = 1
MountProcedure = Enum(Int32ub,
  null = 0,
  mnt = 1,
  dump = 2,
  umnt = 3,
  umntall = 4,
  export = 5
)

MountMntArgs = PascalString(Int32ub, encoding="utf-16-le")

NfsFhandle = Bytes(32)

MountMntRes = Struct(
  "status" / Int32ub,
  "fhandle" / If(this.status == 0, NfsFhandle)
)

RpcCall = Struct(
  "rpcvers" / Const(2, Int32ub),
  "prog" / RpcProgram,
  "vers" / Default(Int32ub, 2),
  "proc" / Switch(this.prog, {
    "portmap": PortmapProcedure,
    "nfs": NfsProcedure,
    "mount": MountProcedure
  }),
  "cred" / RpcOpaqueAuth,
  "verf" / RpcOpaqueAuth
)

RpcMismatchInfo = Struct(
  "low" / Int32ub,
  "high" / Int32ub
)

RpcRejectedReply = Struct(
  "reject_stat" / RpcRejectStat,
  "content" / Switch(this.reject_stat, {
    "rpc_mismatch": RpcMismatchInfo,
    "auth_error": RpcAuthStat
  })
)

RpcAcceptedReply = Struct(
  "verf" / RpcOpaqueAuth,
  "accept_stat" / RpcAcceptStat,
  "content" / Switch(this.accept_stat, {
    "success": GreedyBytes, # content appended
    "prog_mismatch": RpcMismatchInfo
    },
    default=Pass
  )
)

RpcReply = Struct(
  "reply_stat" / RpcReplyStat,
  "content" / Switch(this.reply_stat, {
    "accepted": RpcAcceptedReply,
    "denied": RpcRejectedReply
  })
)

RpcMsg = Struct(
  "xid" / Int32ub,
  "type" / RpcMsgType,
  "content" / Switch(this.type, {
    "call": RpcCall,
    "reply": RpcReply
  })
)

PortmapProc = Struct

NfsStatus = Enum(Int32ub,
  ok = 0,
  err_perm = 1,
  err_noent = 2,
  err_io = 5,
  err_nxio = 6,
  err_acces = 13,
  err_exist = 17,
  err_nodev = 19,
  err_notdir = 20,
  err_isdir = 21,
  err_fbig = 27,
  err_nospc = 28,
  err_rofs = 30,
  err_nametoolong = 63,
  err_notempty = 66,
  err_dquot = 69,
  err_stale = 70,
  err_wflush = 99
)

NfsFtype = Enum(Int32ub,
  none = 0,
  file = 1,
  dir = 2,
  block = 3,
  char = 4,
  link = 5
)

NfsTime = Struct(
  "seconds" / Int32ub,
  "useconds" / Int32ub
)

NfsFattr = Struct(
  "type" / NfsFtype,
  "mode" / Int32ub,
  "nlink" / Int32ub,
  "uid" / Int32ub,
  "gid" / Int32ub,
  "size" / Int32ub,
  "blocksize" / Int32ub,
  "rdev" / Int32ub,
  "blocks" / Int32ub,
  "fsid" / Int32ub,
  "fileid" / Int32ub,
  "atime" / NfsTime,
  "mtime" / NfsTime,
  "ctime" / NfsTime
)

NfsSattr = Struct(
  "mode" / Int32ub,
  "uid" / Int32ub,
  "gid" / Int32ub,
  "size" / Int32ub,
  "atime" / NfsTime,
  "mtime" / NfsTime
)

NfsDiropArgs = Struct(
  "fhandle" / NfsFhandle,
  "name" / PascalString(Int32ub, encoding="utf-16-le")
)

NfsFileopArgs = Struct(
  "fhandle" / NfsFhandle,
  "offset" / Int32ub,
  "count" / Int32ub,
  "totalcount" / Int32ub
)

def getNfsCallStruct(procedure):
  if procedure == "lookup":
    callStruct = NfsDiropArgs
  elif procedure == "getattr":
    callStruct = NfsFhandle
  elif procedure == "read":
    callStruct = NfsFileopArgs
  else:
    raise RuntimeError("NFS call procedure {} not implemented".format(procedure))
  return callStruct

NfsDiropRes = Struct(
  "fhandle" / NfsFhandle,
  "attrs" / NfsFattr
)

NfsFileopRes = Struct(
  "attrs" / NfsFattr,
  "data" / FocusedSeq("data",
    "length" / Int32ub,
    "data" / Bytes(this.length)
  )
)

def getNfsResStruct(procedure):
  if procedure == "lookup":
    resStruct = NfsDiropRes
  elif procedure == "getattr":
    resStruct = NfsFhandle
  elif procedure == "read":
    resStruct = NfsFileopRes
  else:
    raise RuntimeError("NFS result procedure {} not implemented".format(procedure))
  return Struct(
    "status" / NfsStatus,
    "content" / If(this.status == "ok", resStruct)
  )
