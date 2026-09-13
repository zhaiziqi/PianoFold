"""Deterministic difficulty-aware beam search over source onset slices."""

from collections import defaultdict, deque
from dataclasses import dataclass

from pianofold.analysis import analyze_roles
from pianofold.arrangement.candidates import Voicing, generate_voicing_candidates
from pianofold.arrangement.playability import voicing_cost
from pianofold.arrangement.profiles import DifficultyProfile
from pianofold.arrangement.salience import score_salience
from pianofold.symbolic.models import Note, PianoArrangement, PianoNote, ScoreIR


@dataclass(frozen=True, slots=True, eq=False)
class _State:
    score: float
    voicing: Voicing
    source_time: float
    previous: "_State | None"


def _state_order(state: _State) -> tuple:
    return (-state.score, state.voicing.left, state.voicing.right, state.voicing.source_note_ids)


def arrange(
    score: ScoreIR,
    profile: DifficultyProfile,
    beam_width: int = 16,
    melody_note_ids: frozenset[str] = frozenset(),
) -> PianoArrangement:
    """Select piano notes without changing source timing; quantization is upstream.

    Each surviving state stores one voicing and a compact predecessor pointer.
    Hard hand limits apply to simultaneous onset slices, as in the candidate
    model; sustained notes keep their original ends.
    """
    # Fidelity also consumes Voicing, so defer this import until package
    # initialization is complete for callers importing evaluation first.
    from pianofold.evaluation.fidelity import fidelity_score

    if isinstance(beam_width, bool) or not isinstance(beam_width, int) or beam_width <= 0:
        raise ValueError("beam_width must be a positive integer")

    pitched_score = ScoreIR(
        tuple(note for note in score.notes if note.id and note.instrument.casefold() not in {"drum", "drums"}),
        score.tempo_changes,
    )
    if not pitched_score.notes:
        return PianoArrangement((), profile.name)
    roles = analyze_roles(pitched_score)
    salience = score_salience(pitched_score, roles)
    slices: dict[float, list[Note]] = defaultdict(list)
    for note in pitched_score.notes:
        slices[note.start].append(note)

    beam: list[_State] = []
    for start, notes in sorted(slices.items()):
        next_states = []
        required_right_ids = frozenset(note.id for note in notes if note.id in melody_note_ids)
        for candidate in generate_voicing_candidates(notes, salience, profile, required_right_ids):
            reward = profile.fidelity_weight * fidelity_score(notes, candidate, salience)
            if beam:
                # Paths ending at the same voicing have identical future costs:
                # retain only their best predecessor, with stable beam-order ties.
                previous = max(beam, key=lambda state: state.score - voicing_cost(state.voicing, candidate, profile))
                total = previous.score + reward - voicing_cost(previous.voicing, candidate, profile)
            else:
                previous = None
                total = reward - voicing_cost(None, candidate, profile)
            next_states.append(_State(total, candidate, start, previous))
        beam = sorted(next_states, key=_state_order)[:beam_width]

    selected: list[PianoNote] = []
    state = beam[0]
    while state is not None:
        # Voicing stores pitch multiplicities and a slice-wide ID set. Assign
        # unison sources once each, by ID, keeping each source's precise duration.
        sources: dict[int, deque[Note]] = defaultdict(deque)
        retained = set(state.voicing.source_note_ids)
        for note in sorted(slices[state.source_time], key=lambda note: note.id):
            if note.id in retained:
                sources[note.pitch].append(note)
        for hand, pitches in (("left", state.voicing.left), ("right", state.voicing.right)):
            for pitch in pitches:
                note = sources[pitch].popleft()
                selected.append(PianoNote(
                    pitch, note.start, note.end, hand, (note.id,),
                    _expressive_velocity(note, hand, note.id in melody_note_ids or note.id in roles.melody_anchors),
                ))
        state = state.previous

    return PianoArrangement(
        tuple(sorted(selected, key=lambda note: (note.start, note.pitch, note.hand, note.source_note_ids))),
        profile.name,
    )


__all__ = ["arrange"]


def _expressive_velocity(note: Note, hand: str, is_melody: bool) -> int:
    """Give otherwise velocity-less source events a restrained piano dynamic."""
    accent = 5 if round(note.start * 2) % 4 == 0 else 0
    value = 72 + accent + (16 if is_melody else 0) + (6 if hand == "left" else 0)
    return max(1, min(127, value))
