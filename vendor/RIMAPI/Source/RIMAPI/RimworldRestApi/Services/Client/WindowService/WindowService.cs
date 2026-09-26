using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using RIMAPI.Core;
using RIMAPI.Models;
using HarmonyLib;
using RimWorld;
using Verse;

namespace RIMAPI.Services
{
    public class WindowService : IWindowService
    {
        private class NameCandidate
        {
            public string Label;
            public string First;
            public string Second;
        }

        private readonly ConditionalWeakTable<Window, List<NameCandidate>> _nameCandidates =
            new ConditionalWeakTable<Window, List<NameCandidate>>();

        private static List<NameCandidate> BuildNameCandidates(Window window)
        {
            var view = Traverse.Create(window);
            var first = view.Field("curName").GetValue<string>();
            var second = view.Field("curSecondName").GetValue<string>();
            var dual = view.Field("useSecondName").GetValue<bool>();
            var generateFirst = view.Field("nameGenerator").GetValue<Func<string>>();
            var generateSecond = view.Field("secondNameGenerator").GetValue<Func<string>>();
            var result = new List<NameCandidate>();
            for (var index = 0; index < 4; index++)
            {
                var currentFirst = index == 0 ? first : generateFirst?.Invoke();
                var currentSecond = dual ? (index == 0 ? second : generateSecond?.Invoke()) : null;
                if (string.IsNullOrWhiteSpace(currentFirst) || (dual && string.IsNullOrWhiteSpace(currentSecond)))
                    continue;
                var label = dual ? currentFirst + " — " + currentSecond : currentFirst;
                if (result.Any(item => item.Label == label)) continue;
                result.Add(new NameCandidate { Label = label, First = currentFirst, Second = currentSecond });
            }
            return result;
        }

        public ApiResult<List<OpenWindowDto>> ListWindows()
        {
            try
            {
                var windows = Find.WindowStack?.Windows;
                var list = new List<OpenWindowDto>();
                if (windows != null)
                {
                    foreach (var w in windows)
                    {
                        var row = new OpenWindowDto
                        {
                            WindowType = w.GetType().Name,
                            ForcePause = w.forcePause,
                        };
                        if (w is Dialog_NodeTree dialog)
                        {
                            var node = Traverse.Create(dialog).Field("curNode").GetValue<DiaNode>();
                            row.DialogText = node?.text;
                            row.EnabledOptions = node?.options
                                .Where(option => !option.disabled)
                                .Select(option => Traverse.Create(option).Field("text").GetValue<string>())
                                .Where(label => !string.IsNullOrWhiteSpace(label)).ToList()
                                ?? new List<string>();
                        }
                        if (w is Dialog_GiveName && w.GetType().Name.StartsWith("Dialog_NamePlayer"))
                            row.SuggestedNames = _nameCandidates.GetValue(w, BuildNameCandidates)
                                .Select(item => item.Label).ToList();
                        list.Add(row);
                    }
                }
                return ApiResult<List<OpenWindowDto>>.Ok(list);
            }
            catch (Exception ex)
            {
                return ApiResult<List<OpenWindowDto>>.Fail(ex.Message);
            }
        }

        public ApiResult ChooseWindowOption(WindowChooseRequestDto request)
        {
            try
            {
                if (request == null || string.IsNullOrWhiteSpace(request.WindowType)
                    || string.IsNullOrWhiteSpace(request.OptionLabel))
                    return ApiResult.Fail("Window type and option label are required.");
                // Several node-tree dialogs can be stacked. The player can only
                // act on the topmost one; require its text to still match the
                // observation that produced Laya's choice.
                var window = Find.WindowStack?.Windows?.OfType<Dialog_NodeTree>()
                    .LastOrDefault();
                if (window == null || window.GetType().Name != request.WindowType)
                    return ApiResult.Fail("The requested dialogue is no longer the active dialogue.");
                var node = Traverse.Create(window).Field("curNode").GetValue<DiaNode>();
                if (node == null || (request.DialogText != null && node.text != request.DialogText))
                    return ApiResult.Fail("The dialogue changed before the option was selected.");
                var choices = node?.options.Where(option => !option.disabled
                    && Traverse.Create(option).Field("text").GetValue<string>() == request.OptionLabel).ToList();
                if (choices == null || choices.Count != 1)
                    return ApiResult.Fail("The requested enabled option is no longer unique.");
                Traverse.Create(choices[0]).Method("Activate").GetValue();
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                Exception cause = ex.GetBaseException();
                Verse.Log.Error($"[RIMAPI] Dialogue choice failed: {ex}");
                return ApiResult.Fail($"Dialogue choice failed: {cause.GetType().Name}: {cause.Message}");
            }
        }

        public ApiResult ChooseSuggestedName(WindowNameRequestDto request)
        {
            try
            {
                if (request == null || string.IsNullOrWhiteSpace(request.WindowType)
                    || string.IsNullOrWhiteSpace(request.SuggestedName))
                    return ApiResult.Fail("Window type and suggested name are required.");
                var windows = Find.WindowStack?.Windows?
                    .Where(w => w is Dialog_GiveName && w.GetType().Name == request.WindowType).ToList();
                if (windows == null || windows.Count != 1)
                    return ApiResult.Fail("The requested naming dialogue is no longer uniquely open.");
                var window = windows[0];
                var candidates = _nameCandidates.GetValue(window, BuildNameCandidates)
                    .Where(item => item.Label == request.SuggestedName).ToList();
                if (candidates.Count != 1)
                    return ApiResult.Fail("The requested name is not one of this dialogue's suggestions.");
                var candidate = candidates[0];
                var firstValid = AccessTools.Method(window.GetType(), "IsValidName", new[] { typeof(string) });
                var secondValid = AccessTools.Method(window.GetType(), "IsValidSecondName", new[] { typeof(string) });
                var named = AccessTools.Method(window.GetType(), "Named", new[] { typeof(string) });
                var namedSecond = AccessTools.Method(window.GetType(), "NamedSecond", new[] { typeof(string) });
                if (firstValid == null || named == null || !((bool)firstValid.Invoke(window, new object[] { candidate.First })))
                    return ApiResult.Fail("The selected faction or settlement name is invalid.");
                if (candidate.Second != null && (secondValid == null || namedSecond == null
                    || !((bool)secondValid.Invoke(window, new object[] { candidate.Second }))))
                    return ApiResult.Fail("The selected second name is invalid.");
                named.Invoke(window, new object[] { candidate.First });
                if (candidate.Second != null) namedSecond.Invoke(window, new object[] { candidate.Second });
                Find.WindowStack.TryRemove(window, true);
                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult<WindowCloseResultDto> CloseWindows(WindowCloseRequestDto request)
        {
            try
            {
                request = request ?? new WindowCloseRequestDto();
                var windowStack = Find.WindowStack;
                var result = new WindowCloseResultDto();
                if (windowStack?.Windows == null)
                    return ApiResult<WindowCloseResultDto>.Ok(result);

                bool byType = request.WindowTypes != null && request.WindowTypes.Count > 0;

                // Snapshot first — removing mutates the live collection.
                var toClose = windowStack.Windows
                    .Where(w =>
                    {
                        var typeName = w.GetType().Name;
                        if (byType)
                        {
                            return request.WindowTypes.Any(t =>
                                !string.IsNullOrEmpty(t) &&
                                typeName.IndexOf(t, StringComparison.OrdinalIgnoreCase) >= 0);
                        }
                        // No explicit types: close force-pause windows (the
                        // unattended-benchmark nuisance: colony-name dialog,
                        // debug log on error, etc.) when ForcePauseOnly is set.
                        return !request.ForcePauseOnly || w.forcePause;
                    })
                    .ToList();

                foreach (var w in toClose)
                {
                    if (windowStack.TryRemove(w, doCloseSound: false))
                    {
                        result.ClosedCount++;
                        result.ClosedWindows.Add(w.GetType().Name);
                    }
                }

                if (result.ClosedCount > 0)
                {
                    LogApi.Info($"[WindowService] Closed {result.ClosedCount} window(s): "
                        + string.Join(", ", result.ClosedWindows));
                }

                return ApiResult<WindowCloseResultDto>.Ok(result);
            }
            catch (Exception ex)
            {
                return ApiResult<WindowCloseResultDto>.Fail(ex.Message);
            }
        }

        public ApiResult ShowMessage(WindowMessageRequestDto request)
        {
            try
            {
                LongEventHandler.ExecuteWhenFinished(() =>
                {
                    // Create a simple Node with one "OK" option
                    DiaNode node = new DiaNode(request.Text);
                    DiaOption option = new DiaOption(request.ButtonText)
                    {
                        resolveTree = true // Closes the dialog
                    };
                    node.options.Add(option);

                    // Create the Window
                    Dialog_NodeTree window = new Dialog_NodeTree(node, delayInteractivity: false);
                    if (!string.IsNullOrEmpty(request.Title))
                    {
                        // Some versions of RimWorld don't show title on NodeTree, 
                        // but DiaNode doesn't hold title directly usually. 
                        // We can inject it into the text or use a Letter if preferred.
                        // Standard Dialog_NodeTree doesn't always support a top header title 
                        // explicitly distinct from text, but let's try mostly standard usage.
                    }

                    Find.WindowStack.Add(window);
                });

                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }

        public ApiResult ShowDialog(WindowDialogRequestDto request)
        {
            try
            {
                LongEventHandler.ExecuteWhenFinished(() =>
                {
                    DiaNode node = new DiaNode(request.Text);

                    if (request.Options != null)
                    {
                        foreach (var optDto in request.Options)
                        {
                            DiaOption option = new DiaOption(optDto.Label);

                            // Handle closing logic
                            option.resolveTree = optDto.ResolveTree;

                            // Action Logic
                            if (!string.IsNullOrEmpty(optDto.ActionId))
                            {
                                option.action = () =>
                                {
                                    // Log the choice to console (or you could send a callback webhook here)
                                    LogApi.Info($"[WindowService] User selected option: {optDto.Label} (ID: {optDto.ActionId})");
                                };
                            }

                            node.options.Add(option);
                        }
                    }

                    // If no options provided, add a default Close
                    if (node.options.Count == 0)
                    {
                        node.options.Add(new DiaOption("Close") { resolveTree = true });
                    }

                    Dialog_NodeTree window = new Dialog_NodeTree(node, delayInteractivity: false);
                    Find.WindowStack.Add(window);
                });

                return ApiResult.Ok();
            }
            catch (Exception ex)
            {
                return ApiResult.Fail(ex.Message);
            }
        }
    }
}
