const std = @import("std");

const ABI_VERSION: u32 = 1;

const DTYPE_I8: u32 = 1;
const DTYPE_I16: u32 = 2;
const DTYPE_I32: u32 = 3;
const DTYPE_I64: u32 = 4;

const OK: i32 = 0;
const ERR_NULL_POINTER: i32 = 1;
const ERR_UNSUPPORTED_DTYPE: i32 = 2;
const ERR_INVALID_LENGTH: i32 = 3;
const ERR_INVALID_LUT: i32 = 4;
const ERR_CODE_OUT_OF_RANGE: i32 = 5;
const ERR_TARGET_OUT_OF_RANGE: i32 = 6;
const ERR_INTEGER_OVERFLOW: i32 = 7;
const ERR_THREAD_FAILURE: i32 = 8;
const ERR_PYTHON_GATE_REJECTED: i32 = 50;
const ERR_INTERNAL: i32 = 255;

const FLAG_ALLOW_MISSING: u64 = 0x1;
const FLAG_VALIDATE_INPUT: u64 = 0x2;
const FLAG_COLLECT_COUNTS: u64 = 0x4;

const UINT64_MAX: u64 = std.math.maxInt(u64);
const USIZE_MAX: usize = std.math.maxInt(usize);
const ISIZE_MAX_AS_USIZE: usize = @intCast(std.math.maxInt(isize));

const GateReport = extern struct {
    abi_version: u32,
    status: i32,
    flags: u64,
    item_count: u64,
    lut_len: u64,
    target_category_count: u64,
    invalid_input_count: u64,
    invalid_output_count: u64,
    missing_count: u64,
    first_invalid_index: u64,
    first_invalid_code: i64,
    first_invalid_mapped_code: i64,
};

const ExecReport = extern struct {
    abi_version: u32,
    status: i32,
    flags: u64,
    item_count: u64,
    changed_count: u64,
    missing_count: u64,
    invalid_input_count: u64,
    invalid_output_count: u64,
    first_invalid_index: u64,
    first_invalid_code: i64,
    first_invalid_mapped_code: i64,
};

const ValidationResult = struct {
    status: i32 = OK,
    invalid_input_count: u64 = 0,
    invalid_output_count: u64 = 0,
    missing_count: u64 = 0,
    first_invalid_index: u64 = UINT64_MAX,
    first_invalid_code: i64 = 0,
    first_invalid_mapped_code: i64 = 0,

    fn recordInput(self: *ValidationResult, index: usize, code: i64, mapped: i64, status: i32) void {
        self.invalid_input_count += 1;
        self.recordFirst(index, code, mapped, status);
    }

    fn recordOutput(self: *ValidationResult, index: usize, code: i64, mapped: i64, status: i32) void {
        self.invalid_output_count += 1;
        self.recordFirst(index, code, mapped, status);
    }

    fn recordFirst(self: *ValidationResult, index: usize, code: i64, mapped: i64, status: i32) void {
        if (self.status != OK) return;
        self.status = status;
        self.first_invalid_index = @intCast(index);
        self.first_invalid_code = code;
        self.first_invalid_mapped_code = mapped;
    }
};

export fn zhcm_abi_version() callconv(.c) u32 {
    return ABI_VERSION;
}

export fn zhcm_status_message(status: i32) callconv(.c) [*:0]const u8 {
    return switch (status) {
        OK => "ok",
        ERR_NULL_POINTER => "null pointer",
        ERR_UNSUPPORTED_DTYPE => "unsupported dtype",
        ERR_INVALID_LENGTH => "invalid length",
        ERR_INVALID_LUT => "invalid lookup table",
        ERR_CODE_OUT_OF_RANGE => "code out of range",
        ERR_TARGET_OUT_OF_RANGE => "target code out of range",
        ERR_INTEGER_OVERFLOW => "integer overflow",
        ERR_THREAD_FAILURE => "thread failure",
        ERR_PYTHON_GATE_REJECTED => "python gate rejected",
        ERR_INTERNAL => "internal error",
        else => "unknown status",
    };
}

export fn zhcm_predict_remap_lut(
    codes_ptr: ?*const anyopaque,
    item_count: usize,
    dtype: u32,
    lut_ptr: ?[*]const i64,
    lut_len: usize,
    target_category_count: usize,
    missing_code: i64,
    flags: u64,
    out_report: ?*GateReport,
) callconv(.c) i32 {
    initGateReport(out_report, OK, flags, item_count, lut_len, target_category_count);

    const preflight_status = preflight(codes_ptr, null, item_count, dtype, lut_ptr, lut_len, target_category_count, false);
    if (preflight_status != OK) {
        finishGatePreflight(out_report, preflight_status);
        return preflight_status;
    }

    const result = validateByDtype(dtype, codes_ptr.?, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags);
    finishGateValidation(out_report, flags, item_count, lut_len, target_category_count, result);
    return result.status;
}

export fn zhcm_remap_lut_inplace(
    codes_ptr: ?*anyopaque,
    item_count: usize,
    dtype: u32,
    lut_ptr: ?[*]const i64,
    lut_len: usize,
    target_category_count: usize,
    missing_code: i64,
    thread_count: u32,
    flags: u64,
    out_report: ?*ExecReport,
) callconv(.c) i32 {
    _ = thread_count;
    initExecReport(out_report, OK, flags, item_count);

    const read_ptr: ?*const anyopaque = if (codes_ptr) |p| @ptrCast(p) else null;
    const preflight_status = preflight(read_ptr, codes_ptr, item_count, dtype, lut_ptr, lut_len, target_category_count, true);
    if (preflight_status != OK) {
        finishExecPreflight(out_report, preflight_status, flags);
        return preflight_status;
    }

    if ((flags & FLAG_VALIDATE_INPUT) != 0) {
        const result = validateByDtype(dtype, read_ptr.?, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags);
        if (result.status != OK) {
            finishExecValidationFailure(out_report, flags, item_count, result);
            return result.status;
        }
    }

    const stats = remapInplaceByDtype(dtype, codes_ptr.?, item_count, lut_ptr, missing_code, flags);
    finishExecSuccess(out_report, flags, item_count, stats);
    return OK;
}

export fn zhcm_remap_lut_copy(
    src_codes_ptr: ?*const anyopaque,
    dst_codes_ptr: ?*anyopaque,
    item_count: usize,
    dtype: u32,
    lut_ptr: ?[*]const i64,
    lut_len: usize,
    target_category_count: usize,
    missing_code: i64,
    thread_count: u32,
    flags: u64,
    out_report: ?*ExecReport,
) callconv(.c) i32 {
    _ = thread_count;
    initExecReport(out_report, OK, flags, item_count);

    const preflight_status = preflight(src_codes_ptr, dst_codes_ptr, item_count, dtype, lut_ptr, lut_len, target_category_count, true);
    if (preflight_status != OK) {
        finishExecPreflight(out_report, preflight_status, flags);
        return preflight_status;
    }

    if ((flags & FLAG_VALIDATE_INPUT) != 0) {
        const result = validateByDtype(dtype, src_codes_ptr.?, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags);
        if (result.status != OK) {
            finishExecValidationFailure(out_report, flags, item_count, result);
            return result.status;
        }
    }

    const stats = remapCopyByDtype(dtype, src_codes_ptr.?, dst_codes_ptr.?, item_count, lut_ptr, missing_code, flags);
    finishExecSuccess(out_report, flags, item_count, stats);
    return OK;
}

fn initGateReport(
    out_report: ?*GateReport,
    status: i32,
    flags: u64,
    item_count: usize,
    lut_len: usize,
    target_category_count: usize,
) void {
    if (out_report) |report| {
        report.* = .{
            .abi_version = ABI_VERSION,
            .status = status,
            .flags = flags,
            .item_count = @intCast(item_count),
            .lut_len = @intCast(lut_len),
            .target_category_count = @intCast(target_category_count),
            .invalid_input_count = 0,
            .invalid_output_count = 0,
            .missing_count = 0,
            .first_invalid_index = UINT64_MAX,
            .first_invalid_code = 0,
            .first_invalid_mapped_code = 0,
        };
    }
}

fn initExecReport(out_report: ?*ExecReport, status: i32, flags: u64, item_count: usize) void {
    if (out_report) |report| {
        const count_placeholder = if ((flags & FLAG_COLLECT_COUNTS) != 0) 0 else UINT64_MAX;
        report.* = .{
            .abi_version = ABI_VERSION,
            .status = status,
            .flags = flags,
            .item_count = @intCast(item_count),
            .changed_count = count_placeholder,
            .missing_count = count_placeholder,
            .invalid_input_count = 0,
            .invalid_output_count = 0,
            .first_invalid_index = UINT64_MAX,
            .first_invalid_code = 0,
            .first_invalid_mapped_code = 0,
        };
    }
}

fn finishGatePreflight(out_report: ?*GateReport, status: i32) void {
    if (out_report) |report| {
        report.status = status;
    }
}

fn finishGateValidation(
    out_report: ?*GateReport,
    flags: u64,
    item_count: usize,
    lut_len: usize,
    target_category_count: usize,
    result: ValidationResult,
) void {
    if (out_report) |report| {
        report.* = .{
            .abi_version = ABI_VERSION,
            .status = result.status,
            .flags = flags,
            .item_count = @intCast(item_count),
            .lut_len = @intCast(lut_len),
            .target_category_count = @intCast(target_category_count),
            .invalid_input_count = result.invalid_input_count,
            .invalid_output_count = result.invalid_output_count,
            .missing_count = result.missing_count,
            .first_invalid_index = result.first_invalid_index,
            .first_invalid_code = result.first_invalid_code,
            .first_invalid_mapped_code = result.first_invalid_mapped_code,
        };
    }
}

fn finishExecPreflight(out_report: ?*ExecReport, status: i32, flags: u64) void {
    if (out_report) |report| {
        report.status = status;
        if ((flags & FLAG_COLLECT_COUNTS) != 0) {
            report.changed_count = 0;
            report.missing_count = 0;
        }
    }
}

fn finishExecValidationFailure(
    out_report: ?*ExecReport,
    flags: u64,
    item_count: usize,
    result: ValidationResult,
) void {
    if (out_report) |report| {
        const missing_count = if ((flags & FLAG_COLLECT_COUNTS) != 0) result.missing_count else UINT64_MAX;
        report.* = .{
            .abi_version = ABI_VERSION,
            .status = result.status,
            .flags = flags,
            .item_count = @intCast(item_count),
            .changed_count = if ((flags & FLAG_COLLECT_COUNTS) != 0) 0 else UINT64_MAX,
            .missing_count = missing_count,
            .invalid_input_count = result.invalid_input_count,
            .invalid_output_count = result.invalid_output_count,
            .first_invalid_index = result.first_invalid_index,
            .first_invalid_code = result.first_invalid_code,
            .first_invalid_mapped_code = result.first_invalid_mapped_code,
        };
    }
}

fn finishExecSuccess(out_report: ?*ExecReport, flags: u64, item_count: usize, stats: ExecStats) void {
    if (out_report) |report| {
        report.* = .{
            .abi_version = ABI_VERSION,
            .status = OK,
            .flags = flags,
            .item_count = @intCast(item_count),
            .changed_count = if ((flags & FLAG_COLLECT_COUNTS) != 0) stats.changed_count else UINT64_MAX,
            .missing_count = if ((flags & FLAG_COLLECT_COUNTS) != 0) stats.missing_count else UINT64_MAX,
            .invalid_input_count = 0,
            .invalid_output_count = 0,
            .first_invalid_index = UINT64_MAX,
            .first_invalid_code = 0,
            .first_invalid_mapped_code = 0,
        };
    }
}

fn preflight(
    read_ptr: ?*const anyopaque,
    write_ptr: ?*anyopaque,
    item_count: usize,
    dtype: u32,
    lut_ptr: ?[*]const i64,
    lut_len: usize,
    target_category_count: usize,
    require_write_ptr: bool,
) i32 {
    const size = dtypeSize(dtype) orelse return ERR_UNSUPPORTED_DTYPE;

    if (item_count > ISIZE_MAX_AS_USIZE or lut_len > ISIZE_MAX_AS_USIZE or target_category_count > ISIZE_MAX_AS_USIZE) {
        return ERR_INTEGER_OVERFLOW;
    }
    if (item_count > 0 and item_count > USIZE_MAX / size) {
        return ERR_INTEGER_OVERFLOW;
    }

    if (item_count > 0 and read_ptr == null) return ERR_NULL_POINTER;
    if (require_write_ptr and item_count > 0 and write_ptr == null) return ERR_NULL_POINTER;
    if (lut_len > 0 and lut_ptr == null) return ERR_NULL_POINTER;

    return OK;
}

fn dtypeSize(dtype: u32) ?usize {
    return switch (dtype) {
        DTYPE_I8 => @sizeOf(i8),
        DTYPE_I16 => @sizeOf(i16),
        DTYPE_I32 => @sizeOf(i32),
        DTYPE_I64 => @sizeOf(i64),
        else => null,
    };
}

fn validateByDtype(
    dtype: u32,
    codes_ptr: *const anyopaque,
    item_count: usize,
    lut_ptr: ?[*]const i64,
    lut_len: usize,
    target_category_count: usize,
    missing_code: i64,
    flags: u64,
) ValidationResult {
    return switch (dtype) {
        DTYPE_I8 => validateTyped(i8, codes_ptr, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags),
        DTYPE_I16 => validateTyped(i16, codes_ptr, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags),
        DTYPE_I32 => validateTyped(i32, codes_ptr, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags),
        DTYPE_I64 => validateTyped(i64, codes_ptr, item_count, lut_ptr, lut_len, target_category_count, missing_code, flags),
        else => .{ .status = ERR_UNSUPPORTED_DTYPE },
    };
}

fn validateTyped(
    comptime T: type,
    codes_ptr: *const anyopaque,
    item_count: usize,
    lut_ptr: ?[*]const i64,
    lut_len: usize,
    target_category_count: usize,
    missing_code: i64,
    flags: u64,
) ValidationResult {
    var result = ValidationResult{};
    const allow_missing = (flags & FLAG_ALLOW_MISSING) != 0;
    const codes_many: [*]const T = @ptrCast(@alignCast(codes_ptr));
    const codes = codes_many[0..item_count];

    for (codes, 0..) |code_value, index| {
        const old: i64 = @intCast(code_value);
        if (old == missing_code) {
            if (!allow_missing) {
                result.recordInput(index, old, 0, ERR_CODE_OUT_OF_RANGE);
            } else {
                result.missing_count += 1;
            }
            continue;
        }
        if (old < 0) {
            result.recordInput(index, old, 0, ERR_CODE_OUT_OF_RANGE);
            continue;
        }
        const old_index: usize = @intCast(old);
        if (old_index >= lut_len) {
            result.recordInput(index, old, 0, ERR_CODE_OUT_OF_RANGE);
            continue;
        }

        const mapped = lut_ptr.?[old_index];
        if (mapped == missing_code) {
            if (!allow_missing) {
                result.recordOutput(index, old, mapped, ERR_TARGET_OUT_OF_RANGE);
            } else if (!fitsInType(T, mapped)) {
                result.recordOutput(index, old, mapped, ERR_INTEGER_OVERFLOW);
            } else {
                result.missing_count += 1;
            }
            continue;
        }
        if (mapped < 0) {
            result.recordOutput(index, old, mapped, ERR_TARGET_OUT_OF_RANGE);
            continue;
        }
        const mapped_index: usize = @intCast(mapped);
        if (mapped_index >= target_category_count) {
            result.recordOutput(index, old, mapped, ERR_TARGET_OUT_OF_RANGE);
            continue;
        }
        if (!fitsInType(T, mapped)) {
            result.recordOutput(index, old, mapped, ERR_INTEGER_OVERFLOW);
            continue;
        }
    }

    return result;
}

fn fitsInType(comptime T: type, value: i64) bool {
    return value >= std.math.minInt(T) and value <= std.math.maxInt(T);
}

const ExecStats = struct {
    changed_count: u64 = 0,
    missing_count: u64 = 0,
};

fn remapInplaceByDtype(
    dtype: u32,
    codes_ptr: *anyopaque,
    item_count: usize,
    lut_ptr: ?[*]const i64,
    missing_code: i64,
    flags: u64,
) ExecStats {
    return switch (dtype) {
        DTYPE_I8 => remapInplaceTyped(i8, codes_ptr, item_count, lut_ptr, missing_code, flags),
        DTYPE_I16 => remapInplaceTyped(i16, codes_ptr, item_count, lut_ptr, missing_code, flags),
        DTYPE_I32 => remapInplaceTyped(i32, codes_ptr, item_count, lut_ptr, missing_code, flags),
        DTYPE_I64 => remapInplaceTyped(i64, codes_ptr, item_count, lut_ptr, missing_code, flags),
        else => .{},
    };
}

fn remapInplaceTyped(
    comptime T: type,
    codes_ptr: *anyopaque,
    item_count: usize,
    lut_ptr: ?[*]const i64,
    missing_code: i64,
    flags: u64,
) ExecStats {
    var stats = ExecStats{};
    const collect = (flags & FLAG_COLLECT_COUNTS) != 0;
    const codes_many: [*]T = @ptrCast(@alignCast(codes_ptr));
    const codes = codes_many[0..item_count];

    for (codes) |*code| {
        const old: i64 = @intCast(code.*);
        if (old == missing_code) {
            if (collect) stats.missing_count += 1;
            continue;
        }
        const mapped = lut_ptr.?[@intCast(old)];
        if (collect) {
            if (mapped != old) stats.changed_count += 1;
            if (mapped == missing_code) stats.missing_count += 1;
        }
        code.* = @intCast(mapped);
    }
    return stats;
}

fn remapCopyByDtype(
    dtype: u32,
    src_codes_ptr: *const anyopaque,
    dst_codes_ptr: *anyopaque,
    item_count: usize,
    lut_ptr: ?[*]const i64,
    missing_code: i64,
    flags: u64,
) ExecStats {
    return switch (dtype) {
        DTYPE_I8 => remapCopyTyped(i8, src_codes_ptr, dst_codes_ptr, item_count, lut_ptr, missing_code, flags),
        DTYPE_I16 => remapCopyTyped(i16, src_codes_ptr, dst_codes_ptr, item_count, lut_ptr, missing_code, flags),
        DTYPE_I32 => remapCopyTyped(i32, src_codes_ptr, dst_codes_ptr, item_count, lut_ptr, missing_code, flags),
        DTYPE_I64 => remapCopyTyped(i64, src_codes_ptr, dst_codes_ptr, item_count, lut_ptr, missing_code, flags),
        else => .{},
    };
}

fn remapCopyTyped(
    comptime T: type,
    src_codes_ptr: *const anyopaque,
    dst_codes_ptr: *anyopaque,
    item_count: usize,
    lut_ptr: ?[*]const i64,
    missing_code: i64,
    flags: u64,
) ExecStats {
    var stats = ExecStats{};
    const collect = (flags & FLAG_COLLECT_COUNTS) != 0;
    const src_many: [*]const T = @ptrCast(@alignCast(src_codes_ptr));
    const dst_many: [*]T = @ptrCast(@alignCast(dst_codes_ptr));
    const src = src_many[0..item_count];
    const dst = dst_many[0..item_count];

    for (src, 0..) |old_value, index| {
        const old: i64 = @intCast(old_value);
        if (old == missing_code) {
            dst[index] = old_value;
            if (collect) stats.missing_count += 1;
            continue;
        }
        const mapped = lut_ptr.?[@intCast(old)];
        if (collect) {
            if (mapped != old) stats.changed_count += 1;
            if (mapped == missing_code) stats.missing_count += 1;
        }
        dst[index] = @intCast(mapped);
    }
    return stats;
}

test "zhcm_remap_lut_inplace remaps int8 codes and reports counts" {
    var codes = [_]i8{ 0, 1, 2, -1, 1 };
    const lut = [_]i64{ 2, 0, 1 };
    var report: ExecReport = undefined;

    const status = zhcm_remap_lut_inplace(
        codes[0..].ptr,
        codes.len,
        DTYPE_I8,
        lut[0..].ptr,
        lut.len,
        3,
        -1,
        1,
        FLAG_ALLOW_MISSING | FLAG_VALIDATE_INPUT | FLAG_COLLECT_COUNTS,
        &report,
    );

    try std.testing.expectEqual(@as(i32, OK), status);
    try std.testing.expectEqualSlices(i8, &[_]i8{ 2, 0, 1, -1, 0 }, codes[0..]);
    try std.testing.expectEqual(@as(u64, codes.len), report.item_count);
    try std.testing.expectEqual(@as(u64, 4), report.changed_count);
    try std.testing.expectEqual(@as(u64, 1), report.missing_count);
}

test "zhcm_remap_lut_copy leaves source untouched" {
    const src = [_]i32{ 1, 0, -1, 1 };
    var dst = [_]i32{ 9, 9, 9, 9 };
    const lut = [_]i64{ 1, 0 };
    var report: ExecReport = undefined;

    const status = zhcm_remap_lut_copy(
        src[0..].ptr,
        dst[0..].ptr,
        src.len,
        DTYPE_I32,
        lut[0..].ptr,
        lut.len,
        2,
        -1,
        1,
        FLAG_ALLOW_MISSING | FLAG_VALIDATE_INPUT | FLAG_COLLECT_COUNTS,
        &report,
    );

    try std.testing.expectEqual(@as(i32, OK), status);
    try std.testing.expectEqualSlices(i32, &[_]i32{ 1, 0, -1, 1 }, src[0..]);
    try std.testing.expectEqualSlices(i32, &[_]i32{ 0, 1, -1, 0 }, dst[0..]);
    try std.testing.expectEqual(@as(u64, 3), report.changed_count);
    try std.testing.expectEqual(@as(u64, 1), report.missing_count);
}

test "zhcm_predict_remap_lut reports invalid input before mutation" {
    const codes = [_]i16{ 0, 3, 1 };
    const lut = [_]i64{ 0, 1 };
    var report: GateReport = undefined;

    const status = zhcm_predict_remap_lut(
        codes[0..].ptr,
        codes.len,
        DTYPE_I16,
        lut[0..].ptr,
        lut.len,
        2,
        -1,
        FLAG_ALLOW_MISSING | FLAG_COLLECT_COUNTS,
        &report,
    );

    try std.testing.expectEqual(@as(i32, ERR_CODE_OUT_OF_RANGE), status);
    try std.testing.expectEqual(@as(i32, ERR_CODE_OUT_OF_RANGE), report.status);
    try std.testing.expectEqual(@as(u64, 1), report.invalid_input_count);
    try std.testing.expectEqual(@as(u64, 1), report.first_invalid_index);
    try std.testing.expectEqual(@as(i64, 3), report.first_invalid_code);
}
