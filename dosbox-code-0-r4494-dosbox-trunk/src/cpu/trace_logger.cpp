/*
 *  Trace Logger Implementation
 */

#include "trace_logger.h"
#include "cpu.h"
#include "regs.h"
#include <sstream>
#include <iomanip>
#include <cstring>

// Static member initialization
bool TraceLogger::enabled = false;
std::vector<TraceEntry> TraceLogger::traces;
std::string TraceLogger::output_file;
int TraceLogger::step_counter = 0;
CPU_Regs TraceLogger::prev_regs;
Bitu TraceLogger::prev_flags = 0;
bool TraceLogger::state_saved = false;

void TraceLogger::Enable(const std::string& output_path) {
    enabled = true;
    output_file = output_path;
    step_counter = 0;
    traces.clear();
    state_saved = false;
}

void TraceLogger::Disable() {
    enabled = false;
    ExportToJSON();
    Clear();
}

void TraceLogger::SaveState() {
    if (!enabled) return;

    // Save current CPU state
    std::memcpy(&prev_regs, &cpu_regs, sizeof(CPU_Regs));
    prev_flags = reg_flags;
    state_saved = true;
}

void TraceLogger::RecordInstruction(const std::string& instruction, PhysPt address) {
    if (!enabled || !state_saved) return;

    TraceEntry entry;
    entry.step = ++step_counter;
    entry.instruction = instruction;
    entry.address = FormatAddress(address);

    // Compare registers and flags
    CompareRegisters(entry);
    CompareFlags(entry);

    traces.push_back(entry);

    // Save current state for next comparison
    SaveState();
}

void TraceLogger::RecordMemoryWrite(PhysPt address, Bit32u value, int size) {
    if (!enabled || traces.empty()) return;

    TraceEntry& last_entry = traces.back();
    if (!last_entry.memory_write) {
        last_entry.memory_write = new TraceEntry::MemoryWrite();
    }
    last_entry.memory_write->address = FormatAddress(address);
    last_entry.memory_write->value = value;
    last_entry.memory_write->size = size;
}

void TraceLogger::RecordJump(bool jumped, PhysPt target, const std::string& condition) {
    if (!enabled || traces.empty()) return;

    TraceEntry& last_entry = traces.back();
    if (!last_entry.jump_info) {
        last_entry.jump_info = new TraceEntry::JumpInfo();
    }
    last_entry.jump_info->jumped = jumped;
    last_entry.jump_info->target = FormatAddress(target);
    last_entry.jump_info->condition = condition;
}

void TraceLogger::ExportToJSON() {
    if (output_file.empty() || traces.empty()) return;

    std::ofstream file(output_file.c_str());
    if (!file.is_open()) return;

    file << "[\n";

    for (size_t i = 0; i < traces.size(); i++) {
        const TraceEntry& entry = traces[i];

        file << "  {\n";
        file << "    \"step\": " << entry.step << ",\n";
        file << "    \"instruction\": \"" << entry.instruction << "\",\n";
        file << "    \"address\": \"" << entry.address << "\",\n";

        // Register changes
        file << "    \"register_diff\": {";
        for (size_t j = 0; j < entry.register_changes.size(); j++) {
            const auto& reg = entry.register_changes[j];
            if (j > 0) file << ", ";
            file << "\"" << reg.name << "\": {\"before\": " << reg.before
                 << ", \"after\": " << reg.after << "}";
        }
        file << "},\n";

        // Flag changes
        file << "    \"flags_diff\": {";
        for (size_t j = 0; j < entry.flag_changes.size(); j++) {
            const auto& flag = entry.flag_changes[j];
            if (j > 0) file << ", ";
            file << "\"" << flag.name << "\": {\"before\": " << (flag.before ? 1 : 0)
                 << ", \"after\": " << (flag.after ? 1 : 0) << "}";
        }
        file << "},\n";

        // Memory write
        file << "    \"memory_write\": ";
        if (entry.memory_write) {
            file << "{\"address\": \"" << entry.memory_write->address
                 << "\", \"value\": " << entry.memory_write->value
                 << ", \"size\": " << entry.memory_write->size << "}";
        } else {
            file << "null";
        }
        file << ",\n";

        // Jump info
        file << "    \"jump_info\": ";
        if (entry.jump_info) {
            file << "{\"jumped\": " << (entry.jump_info->jumped ? "true" : "false")
                 << ", \"target\": \"" << entry.jump_info->target
                 << "\", \"condition\": \"" << entry.jump_info->condition << "\"}";
        } else {
            file << "null";
        }
        file << "\n";

        file << "  }";
        if (i < traces.size() - 1) file << ",";
        file << "\n";
    }

    file << "]\n";
    file.close();
}

void TraceLogger::Clear() {
    traces.clear();
    step_counter = 0;
    state_saved = false;
}

std::string TraceLogger::FormatAddress(PhysPt address) {
    std::ostringstream oss;
    oss << std::hex << std::uppercase << std::setfill('0');
    oss << std::setw(4) << (address >> 4) << ":" << std::setw(4) << (address & 0xF);
    return oss.str();
}

std::string TraceLogger::GetRegisterName(int index) {
    const char* names[] = {"AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"};
    if (index >= 0 && index < 8) return names[index];
    return "UNKNOWN";
}

std::string TraceLogger::GetFlagName(Bitu flag) {
    switch (flag) {
        case FLAG_CF: return "CF";
        case FLAG_PF: return "PF";
        case FLAG_AF: return "AF";
        case FLAG_ZF: return "ZF";
        case FLAG_SF: return "SF";
        case FLAG_OF: return "OF";
        default: return "UNKNOWN";
    }
}

void TraceLogger::CompareRegisters(TraceEntry& entry) {
    // Compare general purpose registers (AX, CX, DX, BX, SP, BP, SI, DI)
    for (int i = 0; i < 8; i++) {
        Bit16u prev_val = prev_regs.regs[i].word[W_INDEX];
        Bit16u curr_val = cpu_regs.regs[i].word[W_INDEX];

        if (prev_val != curr_val) {
            TraceEntry::RegisterChange change;
            change.name = GetRegisterName(i);
            change.before = prev_val;
            change.after = curr_val;
            entry.register_changes.push_back(change);
        }
    }
}

void TraceLogger::CompareFlags(TraceEntry& entry) {
    // Compare important flags
    Bitu flags_to_check[] = {FLAG_CF, FLAG_PF, FLAG_AF, FLAG_ZF, FLAG_SF, FLAG_OF};

    for (size_t i = 0; i < sizeof(flags_to_check) / sizeof(Bitu); i++) {
        Bitu flag = flags_to_check[i];
        bool prev_set = (prev_flags & flag) != 0;
        bool curr_set = (reg_flags & flag) != 0;

        if (prev_set != curr_set) {
            TraceEntry::FlagChange change;
            change.name = GetFlagName(flag);
            change.before = prev_set;
            change.after = curr_set;
            entry.flag_changes.push_back(change);
        }
    }
}
