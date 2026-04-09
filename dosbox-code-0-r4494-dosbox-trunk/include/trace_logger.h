/*
 *  Trace Logger for 8086 Assembly Teaching
 *  Records instruction execution traces for educational purposes
 */

#ifndef DOSBOX_TRACE_LOGGER_H
#define DOSBOX_TRACE_LOGGER_H

#include "dosbox.h"
#include "regs.h"
#include <string>
#include <vector>
#include <fstream>

// Trace entry structure
struct TraceEntry {
    int step;
    std::string instruction;
    std::string address;

    // Register changes (before -> after)
    struct RegisterChange {
        std::string name;
        Bit32u before;
        Bit32u after;
    };
    std::vector<RegisterChange> register_changes;

    // Flag changes
    struct FlagChange {
        std::string name;
        bool before;
        bool after;
    };
    std::vector<FlagChange> flag_changes;

    // Memory write
    struct MemoryWrite {
        std::string address;
        Bit32u value;
        int size; // 1, 2, or 4 bytes
    };
    MemoryWrite* memory_write;

    // Jump info
    struct JumpInfo {
        bool jumped;
        std::string target;
        std::string condition;
    };
    JumpInfo* jump_info;

    TraceEntry() : step(0), memory_write(nullptr), jump_info(nullptr) {}
    ~TraceEntry() {
        if (memory_write) delete memory_write;
        if (jump_info) delete jump_info;
    }
};

class TraceLogger {
private:
    static bool enabled;
    static std::vector<TraceEntry> traces;
    static std::string output_file;
    static int step_counter;

    // Previous state for comparison
    static CPU_Regs prev_regs;
    static Bitu prev_flags;
    static bool state_saved;

public:
    // Enable/disable tracing
    static void Enable(const std::string& output_path);
    static void Disable();
    static bool IsEnabled() { return enabled; }

    // Save current state (before instruction execution)
    static void SaveState();

    // Record instruction execution (after instruction execution)
    static void RecordInstruction(const std::string& instruction, PhysPt address);

    // Record memory write
    static void RecordMemoryWrite(PhysPt address, Bit32u value, int size);

    // Record jump
    static void RecordJump(bool jumped, PhysPt target, const std::string& condition);

    // Export traces to JSON file
    static void ExportToJSON();

    // Clear all traces
    static void Clear();

private:
    // Helper functions
    static std::string FormatAddress(PhysPt address);
    static std::string GetRegisterName(int index);
    static std::string GetFlagName(Bitu flag);
    static void CompareRegisters(TraceEntry& entry);
    static void CompareFlags(TraceEntry& entry);
};

#endif // DOSBOX_TRACE_LOGGER_H
